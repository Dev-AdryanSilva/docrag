"""Testes da ingestão: leitura de cada formato e divisão em chunks.

Não usam o Chroma nem o modelo de embeddings: testam só a parte que transforma
um arquivo em chunks com a origem certa no metadado.
"""

import zipfile

import pymupdf

from app import ingest
from app.config import settings


def write_docx(path, paragraphs: list[str]) -> None:
    """Cria um .docx mínimo: um zip com o word/document.xml, que é o que o docx2txt lê."""
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as docx:
        docx.writestr("word/document.xml", xml)


def write_pdf(path, pages: list[str]) -> None:
    """Cria um PDF com um texto por página."""
    pdf = pymupdf.open()
    for text in pages:
        pdf.new_page().insert_text((72, 72), text)
    pdf.save(path)
    pdf.close()


def test_txt_utf8(tmp_path):
    path = tmp_path / "politica.txt"
    path.write_text("A matrícula pode ser trancada até o fim do semestre.", encoding="utf-8")

    num_pages, chunks = ingest.load_and_split(str(path), "politica.txt")

    assert num_pages == 0
    assert len(chunks) == 1
    assert "matrícula" in chunks[0].page_content
    assert chunks[0].metadata == {"documento": "politica.txt", "pagina": ingest.NO_PAGE}


def test_txt_latin1_fallback(tmp_path):
    # Arquivos salvos no Bloco de Notas antigo costumam vir em Latin-1, não UTF-8
    path = tmp_path / "antigo.txt"
    path.write_bytes("Estágio obrigatório: 300 horas.".encode("latin-1"))

    _, chunks = ingest.load_and_split(str(path), "antigo.txt")

    assert "Estágio obrigatório" in chunks[0].page_content


def test_txt_empty_has_no_chunks(tmp_path):
    path = tmp_path / "vazio.txt"
    path.write_text("   \n\n  ", encoding="utf-8")

    _, chunks = ingest.load_and_split(str(path), "vazio.txt")

    assert chunks == []


def test_long_text_is_split_with_overlap(tmp_path):
    path = tmp_path / "longo.txt"
    sentences = [f"Esta é a frase número {i} do regulamento." for i in range(200)]
    path.write_text(" ".join(sentences), encoding="utf-8")

    _, chunks = ingest.load_and_split(str(path), "longo.txt")

    assert len(chunks) > 1
    assert all(len(c.page_content) <= settings.chunk_size for c in chunks)
    # Todo chunk guarda de onde veio, para a resposta poder citar a fonte
    assert all(c.metadata["documento"] == "longo.txt" for c in chunks)


def test_docx(tmp_path):
    path = tmp_path / "manual.docx"
    write_docx(path, ["Capítulo 1", "O recesso acontece em julho."])

    num_pages, chunks = ingest.load_and_split(str(path), "manual.docx")

    assert num_pages == 0
    assert "recesso acontece em julho" in chunks[0].page_content
    assert chunks[0].metadata["pagina"] == ingest.NO_PAGE


def test_pdf_keeps_page_numbers(tmp_path):
    path = tmp_path / "edital.pdf"
    write_pdf(path, ["Inscricoes abertas em marco.", "Resultado sai em abril."])

    num_pages, chunks = ingest.load_and_split(str(path), "edital.pdf")

    assert num_pages == 2
    pages = {c.metadata["pagina"]: c.page_content for c in chunks}
    assert "Inscricoes" in pages[1]
    assert "Resultado" in pages[2]


def test_extension_is_case_insensitive(tmp_path):
    path = tmp_path / "NOTAS.TXT"
    path.write_text("Texto em maiúsculas no nome.", encoding="utf-8")

    _, chunks = ingest.load_and_split(str(path), "NOTAS.TXT")

    assert len(chunks) == 1
