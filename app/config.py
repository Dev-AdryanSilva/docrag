from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações lidas das variáveis de ambiente (ou do arquivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    api_key: str

    # LLM (Gemini via Google AI Studio). Flash-Lite: cota gratuita diária bem maior
    # que a do Flash (que é de só 20 requisições/dia no free tier)
    gemini_api_key: str
    gemini_model: str = "gemini-3.1-flash-lite"

    # Regras do RAG
    top_k: int = 4
    # Similaridade mínima (0 a 1) para um chunk contar como "relevante".
    # Baixo de propósito: barra só o que é claramente fora de assunto; o prompt do LLM
    # é a segunda barreira (calibrado com perguntas de teste, ver README)
    similarity_threshold: float = 0.25
    # Quantas trocas (pergunta + resposta) anteriores entram no prompt
    history_turns: int = 4

    # Chunking dos PDFs
    chunk_size: int = 800
    chunk_overlap: int = 100

    # Embeddings (modelo local, funciona bem em português) e banco vetorial
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    chroma_dir: str = "chroma_data"
    chroma_collection: str = "regulamentos"


# Instância única, importada pelos outros módulos
settings = Settings()
