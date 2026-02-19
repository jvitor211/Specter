"""
Modelo: RequisicaoScan.
Log de cada scan feito via API publica.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from specter.modelos.base import Base


class RequisicaoScan(Base):
    __tablename__ = "requisicoes_scan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_sessao: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4
    )
    nome_pacote: Mapped[str] = mapped_column(String(255), nullable=False)
    ecossistema: Mapped[str] = mapped_column(String(20), nullable=False, default="npm")
    versao: Mapped[str | None] = mapped_column(String(100), nullable=True)
    score_risco: Mapped[float | None] = mapped_column(Float, nullable=True)
    sinalizado: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (Index("ix_scan_sessao", "id_sessao"),)

    def __repr__(self) -> str:
        return f"<RequisicaoScan {self.nome_pacote}@{self.versao}>"
