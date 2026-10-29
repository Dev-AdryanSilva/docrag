import logging
import os
import tempfile
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import crud, ingest, rag
from app.db import engine, get_db
from app.models import Base
from app.schemas import (
    AskRequest,
    AskResponse,
    ConversationOut,
    DocumentOut,
    FeedbackIn,
    FeedbackOut,
)
from app.security import require_api_key


logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cria as tabelas que ainda não existem (simples, sem migrações)
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="DocRAG",
    description="Assistente de documentos com RAG: busca híbrida (BM25 + semântica) e LLM, sempre citando a fonte.",
    lifespan=lifespan,
)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Verifica se a API está no ar e se consegue falar com o PostgreSQL."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "banco": "ok"}


@app.post(
    "/documentos",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def upload_document(file: UploadFile, db: Session = Depends(get_db)):
    """Recebe um PDF, Word (.docx) ou TXT, divide em chunks, gera embeddings,
    salva no Chroma e registra no Postgres."""
    # basename evita nomes com caminho (ex.: "../../x.pdf")
    filename = os.path.basename(file.filename or "")
    extension = os.path.splitext(filename)[1].lower()
    if extension not in ingest.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Envie um arquivo PDF, Word (.docx) ou TXT."
        )
    if crud.get_document_by_filename(db, filename):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Esse documento já foi ingerido.")

    # Os leitores precisam de um caminho em disco, então salvamos num arquivo temporário
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
        tmp.write(file.file.read())
    try:
        num_pages, chunks = ingest.load_and_split(tmp.name, filename)
    except Exception:
        logger.exception("Falha ao ler o arquivo %s", filename)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Não foi possível ler o arquivo."
        )
    finally:
        os.remove(tmp.name)

    if not chunks:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Não encontrei texto no arquivo. Se for um PDF escaneado, o OCR precisa "
                "do Tesseract instalado (no Docker ele já vem incluído)."
            ),
        )

    document = crud.create_document(db, filename, num_pages, len(chunks))
    try:
        ingest.index_chunks(document.id, chunks)
    except Exception:
        # Se o Chroma falhar, não deixa um registro sem chunks no Postgres
        crud.delete_document(db, document.id)
        raise
    return document


@app.get("/documentos", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    """Lista os documentos já ingeridos."""
    return crud.list_documents(db)


@app.get("/documentos/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = crud.get_document(db, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Documento não encontrado.")
    return document


@app.delete(
    "/documentos/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Remove um documento do Postgres e seus chunks do Chroma (exige X-API-Key)."""
    if crud.get_document(db, document_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Documento não encontrado.")
    ingest.delete_chunks(document_id)
    crud.delete_document(db, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/perguntar", response_model=AskResponse, dependencies=[Depends(require_api_key)])
def ask(request: AskRequest, db: Session = Depends(get_db)):
    """Responde uma pergunta com base nos documentos, citando as fontes."""
    conversation = None
    history = []
    if request.conversation_id is not None:
        conversation = crud.get_conversation(db, request.conversation_id)
        if conversation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
        # O histórico é lido ANTES de gravar a pergunta atual, para ela não aparecer duplicada
        history = crud.get_history(db, conversation.id)

    try:
        answer, sources = rag.answer_question(request.pergunta, history)
    except Exception:
        # Registra o erro real no log; o usuário vê só uma mensagem genérica
        logger.exception("Falha ao gerar a resposta")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="Falha ao consultar o modelo de linguagem."
        )

    # Só cria a conversa nova depois da resposta pronta: se o LLM falhar, não sobra conversa vazia
    if conversation is None:
        conversation = crud.create_conversation(db)
    crud.add_message(db, conversation.id, "user", request.pergunta)
    message = crud.add_message(db, conversation.id, "assistant", answer, sources)
    return AskResponse(
        resposta=answer, fontes=sources, conversation_id=conversation.id, mensagem_id=message.id
    )


@app.get("/conversas/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Histórico completo de uma conversa."""
    conversation = crud.get_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
    return conversation


@app.post("/feedback", response_model=FeedbackOut, dependencies=[Depends(require_api_key)])
def send_feedback(feedback: FeedbackIn, db: Session = Depends(get_db)):
    """Registra se uma resposta do assistente foi útil ou não."""
    message = crud.get_message(db, feedback.mensagem_id)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mensagem não encontrada.")
    if message.role != "assistant":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Só respostas do assistente recebem feedback."
        )
    saved = crud.save_feedback(db, message.id, feedback.util)
    return FeedbackOut(mensagem_id=saved.message_id, util=saved.useful)