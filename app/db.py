from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# O engine gerencia o pool de conexões com o PostgreSQL
engine = create_engine(settings.database_url, pool_pre_ping=True)

# Cada requisição abre uma sessão a partir desta fábrica
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    """Dependência do FastAPI: abre uma sessão e garante que ela seja fechada."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
