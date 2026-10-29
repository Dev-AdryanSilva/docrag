"""Testes das funções do RAG: busca por palavras-chave, fusão das buscas e montagem das fontes."""

import pytest

from app import ingest, rag
from tests.conftest import make_chunk

A = make_chunk("trecho A", pagina=1)
B = make_chunk("trecho B", pagina=2)
C = make_chunk("trecho C", pagina=3)


class FakeVectorstore:
    """Imita o `get()` do Chroma, que devolve todos os chunks salvos."""

    def __init__(self, chunks):
        self.chunks = chunks

    def get(self):
        return {
            "documents": [c.page_content for c in self.chunks],
            "metadatas": [c.metadata for c in self.chunks],
        }


@pytest.fixture
def fake_vectorstore(monkeypatch):
    def setup(chunks):
        monkeypatch.setattr(ingest, "get_vectorstore", lambda: FakeVectorstore(chunks))
        ingest.get_bm25.cache_clear()  # o índice BM25 fica em cache entre chamadas

    yield setup
    ingest.get_bm25.cache_clear()


def test_keyword_search_finds_exact_term(fake_vectorstore):
    fake_vectorstore([
        make_chunk("O recesso acontece em julho.", pagina=1),
        make_chunk("A matrícula trancada pode ser reaberta no semestre seguinte.", pagina=2),
        make_chunk("As inscrições abrem em março.", pagina=3),
        make_chunk("O estágio obrigatório tem 300 horas.", pagina=4),
        make_chunk("A biblioteca abre às 8h.", pagina=5),
    ])

    results = rag.keyword_search("Posso reabrir uma matrícula TRANCADA?")

    # Maiúsculas e pontuação não atrapalham: o tokenize normaliza a pergunta
    assert results[0].metadata["pagina"] == 2


def test_keyword_search_without_documents(fake_vectorstore):
    fake_vectorstore([])

    assert rag.keyword_search("qualquer coisa") == []


def test_fuse_puts_chunk_found_by_both_searches_first():
    semantic = [A, B]
    keyword = [C, B]

    fused = rag.fuse([semantic, keyword])

    # B aparece nas duas listas, então soma pontos das duas e passa à frente
    assert fused[0] is B
    assert set(c.page_content for c in fused) == {"trecho A", "trecho B", "trecho C"}


def test_fuse_has_no_duplicates():
    fused = rag.fuse([[A, B], [A, B]])

    assert [c.page_content for c in fused] == ["trecho A", "trecho B"]


def test_sources_fallback_when_llm_does_not_cite():
    # Se o LLM não seguiu o formato de citação, mostramos todos os chunks enviados
    sources = rag.build_sources([A, B], "Resposta sem citação nenhuma.")

    assert [s["pagina"] for s in sources] == [1, 2]


def test_citation_needs_the_right_page():
    assert rag.was_cited(A, "(regulamento.pdf, p. 1)")
    assert not rag.was_cited(A, "(regulamento.pdf, p. 2)")


def test_page_10_is_not_a_citation_of_page_1():
    # "p. 1" está contido em "p. 10": a comparação precisa ser do número inteiro
    assert not rag.was_cited(A, "(regulamento.pdf, p. 10)")
