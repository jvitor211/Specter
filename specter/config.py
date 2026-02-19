"""
Configuracao centralizada do Specter.
Carrega variaveis de ambiente com fallbacks sensiveis.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

_RAIZ_PROJETO = Path(__file__).resolve().parent.parent
_ENV_PATH = _RAIZ_PROJETO / ".env"

if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


class Configuracao:
    """Singleton de configuracao — todos os valores vem do ambiente."""

    # --- PostgreSQL ---
    POSTGRES_URL: str = os.getenv(
        "POSTGRES_URL",
        "postgresql://specter:specter_secret@localhost:5432/specter_db",
    )

    # --- Redis ---
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_BACKEND_URL: str = os.getenv("REDIS_BACKEND_URL", "redis://localhost:6379/1")

    # --- GitHub ---
    GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")

    # --- npm ---
    NPM_RATE_LIMIT: int = int(os.getenv("NPM_RATE_LIMIT", "80"))
    NPM_BATCH_SIZE: int = int(os.getenv("NPM_BATCH_SIZE", "100"))
    NPM_LOG_INTERVAL: int = int(os.getenv("NPM_LOG_INTERVAL", "500"))

    # --- Celery ---
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", REDIS_BACKEND_URL)

    # --- LLM ---
    LLM_PROVIDER: str = os.getenv("SPECTER_LLM_PROVIDER", "anthropic")
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

    # --- API ---
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000"
    ).split(",")

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # --- Paths ---
    RAIZ_PROJETO: Path = _RAIZ_PROJETO
    DIR_MODELOS: Path = _RAIZ_PROJETO / "models"
    DIR_DADOS: Path = _RAIZ_PROJETO / "data"


config = Configuracao()
