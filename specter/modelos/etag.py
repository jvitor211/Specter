"""
Modelo: RegistroEtag.
Cache de ETags/cursores para download incremental dos registries.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from specter.modelos.base import Base


class RegistroEtag(Base):
    __tablename__ = "registro_etag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    etag: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ultimo_cursor: Mapped[str | None] = mapped_column(String(512), nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<RegistroEtag endpoint={self.endpoint}>"
