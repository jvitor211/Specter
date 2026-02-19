"""
Modelos: Pacote e VersaoPacote.
Representam o registro de pacotes npm/pypi e suas versoes publicadas.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from specter.modelos.base import Base


class Pacote(Base):
    __tablename__ = "pacotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    ecossistema: Mapped[str] = mapped_column(String(20), nullable=False, default="npm")
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_repositorio: Mapped[str | None] = mapped_column(String(512), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    versoes: Mapped[list["VersaoPacote"]] = relationship(
        back_populates="pacote", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("nome", "ecossistema", name="uq_pacotes_nome_eco"),
        Index("ix_pacotes_nome", "nome"),
        Index("ix_pacotes_ecossistema", "ecossistema"),
    )

    def __repr__(self) -> str:
        return f"<Pacote {self.ecossistema}/{self.nome}>"


class VersaoPacote(Base):
    __tablename__ = "versoes_pacote"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pacote_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pacotes.id", ondelete="CASCADE"), nullable=False
    )
    versao: Mapped[str] = mapped_column(String(100), nullable=False)
    publicado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    contagem_mantenedores: Mapped[int] = mapped_column(Integer, default=0)
    tem_postinstall: Mapped[bool] = mapped_column(Boolean, default=False)
    tem_preinstall: Mapped[bool] = mapped_column(Boolean, default=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    scripts: Mapped[dict] = mapped_column(JSONB, default=dict)
    dependencias: Mapped[dict] = mapped_column(JSONB, default=dict)
    mantenedores: Mapped[list] = mapped_column(JSONB, default=list)
    metadados: Mapped[dict] = mapped_column(JSONB, default=dict)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    pacote: Mapped["Pacote"] = relationship(back_populates="versoes")

    __table_args__ = (
        UniqueConstraint("pacote_id", "versao", name="uq_versao_pacote"),
        Index("ix_versoes_pacote_id", "pacote_id"),
    )

    def __repr__(self) -> str:
        return f"<VersaoPacote {self.pacote_id}@{self.versao}>"
