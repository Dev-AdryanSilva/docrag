"""Testes da autenticação por API key (header X-API-Key).

As rotas que escrevem ou gastam LLM (enviar/apagar documento, perguntar, feedback)
exigem a chave. As de leitura (listar documentos, health) são abertas.
"""

import pytest

from app import ingest

PROTECTED = [
    ("post", "/perguntar", {"json": {"pergunta": "Oi"}}),
    ("post", "/feedback", {"json": {"mensagem_id": 1, "util": True}}),
    ("delete", "/documentos/1", {}),
    ("post", "/documentos", {"files": {"file": ("a.txt", b"texto", "text/plain")}}),
]


@pytest.mark.parametrize("method, url, kwargs", PROTECTED)
def test_protected_route_without_key_returns_401(client, method, url, kwargs):
    response = getattr(client, method)(url, **kwargs)

    assert response.status_code == 401
    assert response.json()["detail"] == "API key inválida ou ausente."


@pytest.mark.parametrize("method, url, kwargs", PROTECTED)
def test_protected_route_with_wrong_key_returns_401(client, method, url, kwargs):
    response = getattr(client, method)(url, headers={"X-API-Key": "chave-errada"}, **kwargs)

    assert response.status_code == 401


def test_public_routes_need_no_key(client):
    assert client.get("/health").status_code == 200
    assert client.get("/documentos").status_code == 200


def test_upload_with_correct_key(client, auth, monkeypatch):
    # O Chroma é simulado: aqui interessa só a autenticação e o registro no banco
    monkeypatch.setattr(ingest, "index_chunks", lambda document_id, chunks: None)

    files = {"file": ("politica.txt", "Home office às sextas.".encode(), "text/plain")}
    response = client.post("/documentos", files=files, headers=auth)

    assert response.status_code == 201
    assert response.json()["filename"] == "politica.txt"
    assert response.json()["num_chunks"] == 1


def test_upload_rejects_unsupported_extension(client, auth):
    files = {"file": ("planilha.xlsx", b"dados", "application/octet-stream")}

    response = client.post("/documentos", files=files, headers=auth)

    assert response.status_code == 400


def test_upload_rejects_duplicate(client, auth, monkeypatch):
    monkeypatch.setattr(ingest, "index_chunks", lambda document_id, chunks: None)
    files = {"file": ("politica.txt", b"Texto qualquer.", "text/plain")}

    client.post("/documentos", files=files, headers=auth)
    response = client.post("/documentos", files=files, headers=auth)

    assert response.status_code == 409
