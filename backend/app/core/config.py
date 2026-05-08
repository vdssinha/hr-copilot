from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # AI provider selection
    AI_LLM_PROVIDER: str = "anthropic"
    AI_EMBEDDER_PROVIDER: str = "anthropic"
    AI_VECTOR_STORE_PROVIDER: str = "chroma"

    AI_LLM_MODEL: str = "claude-sonnet-4-6"
    AI_EMBEDDING_MODEL: str = "voyage-3"

    # API keys
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "sqlite:///./cbnest.db"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Vector store
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    BACKEND_BASE_URL: str = "http://localhost:8000"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
