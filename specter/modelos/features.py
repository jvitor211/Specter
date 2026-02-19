"""
Modelo: FeaturePacote.
Features computadas para cada pacote, usadas como input do modelo ML.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column

from specter.modelos.base import Base


class FeaturePacote(Base):
    __tablename__ = "features_pacote"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pacote_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pacotes.id", ondelete="CASCADE"), nullable=False
    )
    versao_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("versoes_pacote.id", ondelete="SET NULL"), nullable=True
    )

    # Temporais
    idade_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dias_desde_ultima_publicacao: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    total_versoes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frequencia_versoes: Mapped[float | None] = mapped_column(Float, nullable=True)
    pacote_novo: Mapped[bool] = mapped_column(Boolean, default=False)

    # Sociais
    contagem_mantenedores: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mantenedor_unico: Mapped[bool] = mapped_column(Boolean, default=False)
    tem_github: Mapped[bool] = mapped_column(Boolean, default=False)
    estrelas_github: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idade_github_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contribuidores_github: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Risco comportamental
    tem_script_postinstall: Mapped[bool] = mapped_column(Boolean, default=False)
    tem_script_preinstall: Mapped[bool] = mapped_column(Boolean, default=False)
    tamanho_script_instalacao: Mapped[int] = mapped_column(Integer, default=0)

    # Typosquatting
    score_typosquatting: Mapped[float | None] = mapped_column(Float, nullable=True)
    distancia_edicao_minima: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provavel_typosquat: Mapped[bool] = mapped_column(Boolean, default=False)

    # Score final
    score_risco: Mapped[float | None] = mapped_column(Float, nullable=True)
    computado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_features_pacote_id", "pacote_id"),
        Index("ix_features_score_risco", "score_risco"),
    )

    def __repr__(self) -> str:
        return f"<FeaturePacote pacote={self.pacote_id} score={self.score_risco}>"
