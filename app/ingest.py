import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import docx2txt
import pymupdf4llm
from langchain_chroma import Chroma
from langchain_core.documents import Document as Chunk
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi

from app.config import settings

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt")
# Word e TXT não têm páginas fixas; guardamos 0 no lugar do número da página
NO_PAGE = 0


@lru_cache
def get_embeddings() -> HuggingFaceEmbeddings:
    """Carrega o modelo de embeddings uma única vez (a primeira chamada baixa o modelo)."""
    return HuggingFaceEmbeddings(model_name=settings.embedding_model)


@lru_cache
def get_vectorstore() -> Chroma:
    """Abre (ou cria) a coleção do Chroma, persistida em disco."""
    return Chroma(
        collection_name=settings.chroma_collection,
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_dir,
        # Distância de cosseno: facilita converter em similaridade (0 a 1) na etapa 4
        collection_metadata={"hnsw:space": "cosine"},
    )


# Palavras comuns que aparecem em quase todo texto e não ajudam a achar o trecho certo.
# Sem esta lista, "que", "o" e "para" contavam como palavras-chave no BM25 (já sem acento)
STOPWORDS = frozenset(
    """
    a ao aos as com como da das de do dos e ela ele em entao essa esse esta este eu foi
    ha isso ja mais mas me meu minha na nas no nos o onde os ou outra outro para pela pelo
    por qual quais quando quanto quantos quantas que se sem ser seu sua sao sobre tem ter
    um uma voce
    """.split()
)


def tokenize(text: str) -> list[str]:
    """Prepara o texto para o BM25: minúsculas, sem acentos, sem pontuação e sem stopwords.

    Sem acentos porque é comum digitar "curriculo" para achar "currículo".
    """
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return [word for word in re.findall(r"\w+", text) if word not in STOPWORDS]


@lru_cache
def get_bm25() -> tuple[BM25Okapi, list[Chunk]] | None:
    """Monta o índice de palavras-chave (BM25) com todos os chunks salvos no Chroma.

    Devolve o índice e a lista de chunks na mesma ordem (o BM25 só guarda as palavras).
    Fica em cache; é refeito sempre que um documento é adicionado ou removido.
    """
    data = get_vectorstore().get()
    if not data["documents"]:
        return None
    chunks = [
        Chunk(page_content=text, metadata=metadata)
        for text, metadata in zip(data["documents"], data["metadatas"])
    ]
    return BM25Okapi([tokenize(c.page_content) for c in chunks]), chunks


# ---------- Leitura de cada formato: devolve uma lista de (página, texto) ----------


def read_pdf(path: str) -> list[tuple[int, str]]:
    """Lê o PDF página a página, em Markdown.

    O PyMuPDF4LLM analisa o layout: tabelas viram tabelas Markdown e textos em duas
    colunas saem na ordem de leitura. Páginas sem texto (PDF escaneado) passam por
    OCR com o Tesseract em português, quando ele está instalado (no Docker, está).
    """
    pages = pymupdf4llm.to_markdown(path, page_chunks=True, ocr_language="por")
    return [(page["metadata"]["page_number"], page["text"]) for page in pages]


def read_docx(path: str) -> list[tuple[int, str]]:
    """Extrai o texto de um arquivo do Word (.docx)."""
    return [(NO_PAGE, docx2txt.process(path))]


def read_txt(path: str) -> list[tuple[int, str]]:
    """Lê um arquivo de texto. Tenta UTF-8 e, se falhar, Latin-1 (comum no Windows)."""
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return [(NO_PAGE, text)]


READERS = {".pdf": read_pdf, ".docx": read_docx, ".txt": read_txt}


def load_and_split(path: str, filename: str) -> tuple[int, list[Chunk]]:
    """Lê o arquivo e divide em chunks. Retorna (nº de páginas, chunks).

    Para Word e TXT, o nº de páginas é 0 (esses formatos não têm páginas fixas).
    """
    extension = Path(filename).suffix.lower()
    pages = READERS[extension](path)

    # Cada página vira um Document com a sua origem no metadado (usado para citar a fonte)
    documents = [
        Chunk(page_content=text, metadata={"documento": filename, "pagina": page})
        for page, text in pages
        if text.strip()
    ]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    chunks = splitter.split_documents(documents)

    num_pages = len(pages) if extension == ".pdf" else 0
    return num_pages, chunks


def index_chunks(document_id: int, chunks: list[Chunk]) -> None:
    """Gera os embeddings dos chunks e salva no Chroma, ligados ao id do documento."""
    for chunk in chunks:
        chunk.metadata["document_id"] = document_id
    get_vectorstore().add_documents(chunks)
    get_bm25.cache_clear()  # o índice BM25 precisa incluir os chunks novos


def delete_chunks(document_id: int) -> None:
    """Remove do Chroma todos os chunks de um documento."""
    get_vectorstore().delete(where={"document_id": document_id})
    get_bm25.cache_clear()
