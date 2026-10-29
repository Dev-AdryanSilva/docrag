from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import settings

# auto_error=False: quem decide a resposta de erro somos nós (401 em português)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Depends(api_key_header)) -> None:
    """Dependência que bloqueia a rota se o header X-API-Key estiver errado ou ausente."""
    if api_key != settings.api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="API key inválida ou ausente.")
