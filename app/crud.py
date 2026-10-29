from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Conversation, Document, Feedback, Message


def create_document(db: Session, filename: str, num_pages: int, num_chunks: int) -> Document:
    document = Document(filename=filename, num_pages=num_pages, num_chunks=num_chunks)
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def list_documents(db: Session) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.id)))


def get_document(db: Session, document_id: int) -> Document | None:
    return db.get(Document, document_id)


def get_document_by_filename(db: Session, filename: str) -> Document | None:
    return db.scalar(select(Document).where(Document.filename == filename))


def delete_document(db: Session, document_id: int) -> bool:
    """Remove o registro. Retorna False se o documento não existir."""
    document = db.get(Document, document_id)
    if document is None:
        return False
    db.delete(document)
    db.commit()
    return True


def create_conversation(db: Session) -> Conversation:
    conversation = Conversation()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation(db: Session, conversation_id: int) -> Conversation | None:
    return db.get(Conversation, conversation_id)


def get_history(db: Session, conversation_id: int) -> list[dict]:
    """Últimas trocas da conversa (pergunta + resposta), da mais antiga para a mais recente."""
    limit = settings.history_turns * 2
    recent = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    return [{"role": m.role, "content": m.content} for m in reversed(list(recent))]


def add_message(
    db: Session, conversation_id: int, role: str, content: str, sources: list[dict] | None = None
) -> Message:
    message = Message(conversation_id=conversation_id, role=role, content=content, sources=sources or [])
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_message(db: Session, message_id: int) -> Message | None:
    return db.get(Message, message_id)


def save_feedback(db: Session, message_id: int, useful: bool) -> Feedback:
    """Grava o feedback da mensagem; se ela já tinha um, atualiza (1 por mensagem)."""
    feedback = db.scalar(select(Feedback).where(Feedback.message_id == message_id))
    if feedback is None:
        feedback = Feedback(message_id=message_id, useful=useful)
        db.add(feedback)
    else:
        feedback.useful = useful
    db.commit()
    db.refresh(feedback)
    return feedback