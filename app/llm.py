"""Único ponto do projeto que conversa com o LLM.

Para trocar o Gemini por Groq ou Ollama, basta reescrever `generate` mantendo a mesma
assinatura: recebe uma lista de mensagens {"role", "content"} e devolve o texto da resposta.
O resto da aplicação (rag.py, main.py) não precisa mudar.
"""

from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings

# O LangChain usa "human" e "ai" no lugar de "user" e "assistant"
_ROLES = {"system": "system", "user": "human", "assistant": "ai"}


@lru_cache
def _get_client() -> ChatGoogleGenerativeAI:
    # temperature=0: respostas mais estáveis e fiéis ao contexto
    # max_retries/timeout: se a API estiver sobrecarregada, falha rápido em vez de travar
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
        max_retries=2,
        timeout=30,
    )


def generate(messages: list[dict]) -> str:
    """Envia as mensagens ao modelo e devolve o texto da resposta."""
    langchain_messages = [(_ROLES[m["role"]], m["content"]) for m in messages]
    return _get_client().invoke(langchain_messages).text
