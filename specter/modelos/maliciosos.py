"""
Modelo: MaliciosoConhecido.
Ground truth para treino — pacotes confirmados como maliciosos (OSV, Socket, manual).
"""

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from specter.modelos.base import Base


class MaliciosoConhecido(Base):
    __tablename__ = "maliciosos_conhecidos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pacote_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pacotes.id", ondelete="CASCADE"), nullable=False
    )
    fonte: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    confirmado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("pacote_id", "fonte", name="uq_malicioso_pacote_fonte"),
        Index("ix_maliciosos_pacote", "pacote_id"),
    )

    def __repr__(self) -> str:
        return f"<MaliciosoConhecido pacote={self.pacote_id} fonte={self.fonte}>"
