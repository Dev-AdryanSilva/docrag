from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    """Como um documento aparece nas respostas da API."""

    # from_attributes permite montar o schema direto de um objeto SQLAlchemy
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    # 0 para Word e TXT, que não têm páginas fixas
    num_pages: int
    num_chunks: int
    created_at: datetime


class Source(BaseModel):
    """Trecho de documento usado para montar uma resposta."""

    documento: str
    # None quando o documento não tem páginas (Word e TXT)
    pagina: int | None
    trecho: str


class AskRequest(BaseModel):
    pergunta: str = Field(min_length=1, max_length=1000)
    # Se vier vazio, uma nova conversa é criada
    conversation_id: int | None = None


class AskResponse(BaseModel):
    resposta: str
    fontes: list[Source]
    conversation_id: int
    # Id da mensagem do assistente, usado para enviar o feedback
    mensagem_id: int


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    sources: list[Source]
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    messages: list[MessageOut]


class FeedbackIn(BaseModel):
    mensagem_id: int
    util: bool


class FeedbackOut(BaseModel):
    mensagem_id: int
    util: bool
