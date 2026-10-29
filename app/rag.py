import re

from langchain_core.documents import Document as Chunk

from app import llm
from app.config import settings
from app.ingest import NO_PAGE, get_bm25, get_vectorstore

NOT_FOUND_MESSAGE = "Não encontrei essa informação nos documentos."

SYSTEM_PROMPT = """Você é um assistente que responde perguntas sobre os documentos enviados pelo usuário.

Regras:
- Responda SOMENTE com base no contexto abaixo. Não use conhecimento externo.
- Se o contexto não contiver a resposta, responda exatamente: "{not_found}"
- Cite as fontes no formato (nome-do-documento, p. N). Se a fonte não tiver página, use (nome-do-documento).
- O contexto pode conter tabelas em Markdown: leia linha e coluna com cuidado.
- Seja objetivo e responda em português.

Contexto:
{context}"""

EXCERPT_SIZE = 300
RRF_K = 60  # constante padrão do Reciprocal Rank Fusion


def semantic_search(question: str) -> list[tuple[Chunk, float]]:
    """Busca semântica: os top-k chunks com significado parecido, com a similaridade de cada um."""
    results = get_vectorstore().similarity_search_with_score(question, k=settings.top_k)
    # O Chroma devolve distância de cosseno (menor = mais parecido); convertemos em similaridade
    return [(chunk, 1 - distance) for chunk, distance in results]


def keyword_search(question: str) -> list[Chunk]:
    """Busca por palavras-chave (BM25): os top-k chunks que contêm os termos da pergunta."""
    bm25 = get_bm25()
    return bm25.invoke(question) if bm25 else []


def fuse(rankings: list[list[Chunk]]) -> list[Chunk]:
    """Junta várias listas ordenadas numa só (Reciprocal Rank Fusion).

    Cada chunk ganha 1 / (RRF_K + posição) em cada lista onde aparece. Assim, quem vai
    bem nas duas buscas sobe, e não precisamos comparar notas de escalas diferentes.
    """
    scores: dict[tuple, float] = {}
    chunks: dict[tuple, Chunk] = {}
    for ranking in rankings:
        for position, chunk in enumerate(ranking, start=1):
            key = (chunk.metadata["documento"], chunk.metadata["pagina"], chunk.page_content)
            chunks[key] = chunk
            scores[key] = scores.get(key, 0) + 1 / (RRF_K + position)
    best = sorted(scores, key=scores.get, reverse=True)[: settings.top_k]
    return [chunks[key] for key in best]


def source_label(chunk: Chunk) -> str:
    """'regulamento.pdf, p. 2' para PDF; só 'politica.docx' para Word e TXT (sem páginas)."""
    page = chunk.metadata["pagina"]
    name = chunk.metadata["documento"]
    return name if page == NO_PAGE else f"{name}, p. {page}"


def build_context(chunks: list[Chunk]) -> str:
    """Junta os chunks num texto único, cada um identificado pela sua fonte."""
    return "\n\n".join(f"[Fonte: {source_label(c)}]\n{c.page_content}" for c in chunks)


def was_cited(chunk: Chunk, answer: str) -> bool:
    """Diz se o LLM citou este chunk na resposta (documento e, quando existe, a página)."""
    page = chunk.metadata["pagina"]
    # \b: "p. 1" não pode casar com "p. 10"
    return chunk.metadata["documento"] in answer and (
        page == NO_PAGE or re.search(rf"p\. {page}\b", answer) is not None
    )


def build_sources(chunks: list[Chunk], answer: str) -> list[dict]:
    """Monta as fontes, mantendo só os chunks que o LLM citou na resposta."""
    cited = [c for c in chunks if was_cited(c, answer)]
    # Se o LLM não seguiu o formato de citação, mostramos todos os chunks enviados a ele
    return [
        {
            "documento": c.metadata["documento"],
            # Word e TXT não têm página: a API devolve null
            "pagina": None if c.metadata["pagina"] == NO_PAGE else c.metadata["pagina"],
            "trecho": c.page_content[:EXCERPT_SIZE],
        }
        for c in (cited or chunks)
    ]


def answer_question(question: str, history: list[dict]) -> tuple[str, list[dict]]:
    """Responde a pergunta usando só os documentos.

    `history` é a lista de mensagens anteriores ({"role", "content"}), da mais antiga
    para a mais recente. Retorna (resposta, fontes).
    """
    semantic = semantic_search(question)

    # Se nem o chunk mais parecido passa do limiar, a pergunta está fora do assunto
    # dos documentos: responde sem gastar uma chamada ao LLM
    if not semantic or max(similarity for _, similarity in semantic) < settings.similarity_threshold:
        return NOT_FOUND_MESSAGE, []

    # Busca híbrida: a semântica entende sinônimos; o BM25 acha termos exatos
    # ("trancada", "recesso") mesmo quando um PDF grande domina a busca semântica
    chunks = fuse([[chunk for chunk, _ in semantic], keyword_search(question)])

    # O LLM recebe os chunks combinados e decide o que é relevante
    system = SYSTEM_PROMPT.format(not_found=NOT_FOUND_MESSAGE, context=build_context(chunks))
    messages = [{"role": "system", "content": system}, *history]
    messages.append({"role": "user", "content": question})
    answer = llm.generate(messages).strip()

    # Se o próprio LLM disse que não achou, não faz sentido mostrar fontes
    if answer.startswith(NOT_FOUND_MESSAGE.rstrip(".")):
        return NOT_FOUND_MESSAGE, []
    return answer, build_sources(chunks, answer)
