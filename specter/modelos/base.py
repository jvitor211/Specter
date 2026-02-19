"""
Base declarativa e fabrica de sessoes.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from specter.config import config

_engine = None
_SessionLocal = None


class Base(DeclarativeBase):
    pass


def obter_engine():
    """Retorna engine singleton. Cria na primeira chamada."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            config.POSTGRES_URL,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine


def obter_sessao() -> Session:
    """Retorna uma nova sessao do banco."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=obter_engine(), expire_on_commit=False)
    return _SessionLocal()
