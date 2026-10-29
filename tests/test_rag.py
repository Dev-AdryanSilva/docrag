"""Testes das funções puras do RAG: fusão das buscas e montagem das fontes."""

from app import rag
from tests.conftest import make_chunk

A = make_chunk("trecho A", pagina=1)
B = make_chunk("trecho B", pagina=2)
C = make_chunk("trecho C", pagina=3)


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
