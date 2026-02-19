"""
Modelos: ChaveAPI e LogUso.
Sistema de autenticacao por API key com tiers e metricas de uso.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from specter.modelos.base import Base


class ChaveAPI(Base):
    __tablename__ = "chaves_api"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hash_chave: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    requisicoes_mes: Mapped[int] = mapped_column(Integer, default=0)
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ultimo_uso_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ChaveAPI tier={self.tier} email={self.email}>"


class LogUso(Base):
    __tablename__ = "logs_uso"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave_api_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chaves_api.id", ondelete="CASCADE"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp_req: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    tempo_resposta_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pacotes_escaneados: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<LogUso chave={self.chave_api_id} endpoint={self.endpoint}>"
