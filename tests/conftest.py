"""Configuração compartilhada dos testes.

As variáveis de ambiente são definidas ANTES de importar o app, porque `app.config`
lê as configurações no momento do import. Assim os testes não dependem do .env,
do PostgreSQL nem da chave do Gemini.
"""

import os
import tempfile

TEST_DIR = tempfile.mkdtemp(prefix="docrag-tests-")
TEST_API_KEY = "chave-de-teste"

os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(TEST_DIR, 'test.db')}"
os.environ["API_KEY"] = TEST_API_KEY
os.environ["GEMINI_API_KEY"] = "chave-falsa"
os.environ["CHROMA_DIR"] = os.path.join(TEST_DIR, "chroma")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from langchain_core.documents import Document as Chunk  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture
def client():
    """Cliente HTTP da API com um banco vazio a cada teste."""
    Base.metadata.drop_all(engine)
    with TestClient(app) as test_client:  # o "with" roda o lifespan, que cria as tabelas
        yield test_client


@pytest.fixture
def auth():
    """Header com a API key correta."""
    return {"X-API-Key": TEST_API_KEY}


def make_chunk(text: str, documento: str = "regulamento.pdf", pagina: int = 1) -> Chunk:
    """Cria um chunk igual aos que a ingestão salva no Chroma."""
    return Chunk(page_content=text, metadata={"documento": documento, "pagina": pagina})
