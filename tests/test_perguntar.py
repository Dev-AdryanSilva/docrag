"""Testes do endpoint /perguntar com o LLM e as buscas simulados.

As duas buscas (semântica e BM25) e o `llm.generate` são trocados por funções falsas.
Assim testamos as regras da API e do RAG (limiar, citação de fontes, histórico,
tratamento de erro) sem chamar o Gemini e sem carregar o modelo de embeddings.
"""

import pytest

from app import llm, rag
from app.config import settings
from tests.conftest import make_chunk

CHUNK_P1 = make_chunk("Inscrições de estágio abrem em março.", pagina=1)
CHUNK_P3 = make_chunk("O estágio obrigatório tem 300 horas.", pagina=3)


class FakeLLM:
    """Substitui o Gemini: devolve uma resposta fixa e guarda as mensagens recebidas."""

    def __init__(self, answer: str):
        self.answer = answer
        self.calls: list[list[dict]] = []

    def __call__(self, messages: list[dict]) -> str:
        self.calls.append(messages)
        return self.answer


@pytest.fixture
def fake_search(monkeypatch):
    """Faz as buscas devolverem chunks fixos. A similaridade pode ser trocada no teste."""

    def setup(similarity: float = 0.8, chunks=(CHUNK_P1, CHUNK_P3)):
        monkeypatch.setattr(rag, "semantic_search", lambda q: [(c, similarity) for c in chunks])
        monkeypatch.setattr(rag, "keyword_search", lambda q: list(chunks))

    return setup


@pytest.fixture
def fake_llm(monkeypatch):
    def setup(answer: str) -> FakeLLM:
        fake = FakeLLM(answer)
        monkeypatch.setattr(llm, "generate", fake)
        return fake

    return setup


def test_below_threshold_answers_not_found_without_calling_llm(client, auth, fake_search, fake_llm):
    fake_search(similarity=settings.similarity_threshold - 0.01)
    fake = fake_llm("não deveria ser usado")

    response = client.post("/perguntar", json={"pergunta": "Qual a capital da França?"}, headers=auth)

    assert response.status_code == 200
    assert response.json()["resposta"] == rag.NOT_FOUND_MESSAGE
    assert response.json()["fontes"] == []
    assert fake.calls == []  # o limiar economiza a chamada ao LLM


def test_answer_shows_only_cited_sources(client, auth, fake_search, fake_llm):
    fake_search()
    fake = fake_llm("O estágio obrigatório tem 300 horas (regulamento.pdf, p. 3).")

    response = client.post("/perguntar", json={"pergunta": "Quantas horas de estágio?"}, headers=auth)

    body = response.json()
    assert response.status_code == 200
    assert "300 horas" in body["resposta"]
    # Os dois chunks foram para o LLM, mas só a página citada aparece como fonte
    assert body["fontes"] == [
        {"documento": "regulamento.pdf", "pagina": 3, "trecho": CHUNK_P3.page_content}
    ]

    system, *_, user = fake.calls[0]
    assert "[Fonte: regulamento.pdf, p. 1]" in system["content"]
    assert "[Fonte: regulamento.pdf, p. 3]" in system["content"]
    assert user == {"role": "user", "content": "Quantas horas de estágio?"}


def test_llm_not_found_returns_no_sources(client, auth, fake_search, fake_llm):
    fake_search()
    fake_llm("Não encontrei essa informação nos documentos.")

    response = client.post("/perguntar", json={"pergunta": "Tem refeitório?"}, headers=auth)

    assert response.json()["resposta"] == rag.NOT_FOUND_MESSAGE
    assert response.json()["fontes"] == []


def test_document_without_pages_returns_null_page(client, auth, fake_search, fake_llm):
    chunk = make_chunk("Home office às sextas.", documento="politica.docx", pagina=0)
    fake_search(chunks=[chunk])
    fake_llm("Sim, às sextas (politica.docx).")

    response = client.post("/perguntar", json={"pergunta": "Tem home office?"}, headers=auth)

    assert response.json()["fontes"][0]["pagina"] is None


def test_llm_failure_returns_502_and_saves_nothing(client, auth, fake_search, monkeypatch):
    fake_search()

    def broken_llm(messages):
        raise TimeoutError("Gemini fora do ar")

    monkeypatch.setattr(llm, "generate", broken_llm)

    response = client.post("/perguntar", json={"pergunta": "Quantas horas?"}, headers=auth)

    assert response.status_code == 502
    assert response.json()["detail"] == "Falha ao consultar o modelo de linguagem."
    # A conversa só é criada depois da resposta pronta: nada ficou salvo
    assert client.get("/conversas/1").status_code == 404


def test_follow_up_question_sends_history(client, auth, fake_search, fake_llm):
    fake_search()
    fake = fake_llm("São 300 horas (regulamento.pdf, p. 3).")

    first = client.post("/perguntar", json={"pergunta": "Quantas horas?"}, headers=auth).json()
    client.post(
        "/perguntar",
        json={"pergunta": "E se eu reprovar?", "conversation_id": first["conversation_id"]},
        headers=auth,
    )

    # A segunda chamada ao LLM recebe a troca anterior antes da pergunta nova
    second_call = fake.calls[1]
    assert second_call[1] == {"role": "user", "content": "Quantas horas?"}
    assert second_call[2] == {"role": "assistant", "content": "São 300 horas (regulamento.pdf, p. 3)."}
    assert second_call[3] == {"role": "user", "content": "E se eu reprovar?"}

    conversation = client.get(f"/conversas/{first['conversation_id']}").json()
    assert [m["role"] for m in conversation["messages"]] == ["user", "assistant", "user", "assistant"]


def test_follow_up_searches_with_previous_question(client, auth, fake_llm, monkeypatch):
    # "E a outra experiência?" sozinha não diz o assunto: a busca precisa da pergunta anterior
    queries = []

    def semantic(query):
        queries.append(query)
        return [(CHUNK_P3, 0.8)]

    monkeypatch.setattr(rag, "semantic_search", semantic)
    monkeypatch.setattr(rag, "keyword_search", lambda query: [])
    fake_llm("Resposta (regulamento.pdf, p. 3).")

    first = client.post("/perguntar", json={"pergunta": "Quais experiências tem o currículo?"}, headers=auth).json()
    client.post(
        "/perguntar",
        json={"pergunta": "E a outra experiência?", "conversation_id": first["conversation_id"]},
        headers=auth,
    )

    assert queries == [
        "Quais experiências tem o currículo?",
        "Quais experiências tem o currículo? E a outra experiência?",
    ]


def test_unknown_conversation_returns_404(client, auth, fake_search, fake_llm):
    fake_search()
    fake_llm("qualquer coisa")

    response = client.post("/perguntar", json={"pergunta": "Oi", "conversation_id": 999}, headers=auth)

    assert response.status_code == 404


def test_empty_question_is_rejected(client, auth):
    response = client.post("/perguntar", json={"pergunta": ""}, headers=auth)

    assert response.status_code == 422


def test_feedback_only_on_assistant_messages(client, auth, fake_search, fake_llm):
    fake_search()
    fake_llm("São 300 horas (regulamento.pdf, p. 3).")
    answer = client.post("/perguntar", json={"pergunta": "Quantas horas?"}, headers=auth).json()

    ok = client.post("/feedback", json={"mensagem_id": answer["mensagem_id"], "util": True}, headers=auth)
    # A mensagem anterior à resposta é a pergunta do usuário
    user_message_id = answer["mensagem_id"] - 1
    rejected = client.post("/feedback", json={"mensagem_id": user_message_id, "util": True}, headers=auth)

    assert ok.json() == {"mensagem_id": answer["mensagem_id"], "util": True}
    assert rejected.status_code == 400
