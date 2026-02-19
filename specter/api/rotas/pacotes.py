"""
Rota GET /v1/package/{ecossistema}/{nome} — historico de risco de um pacote.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from specter.modelos.base import obter_sessao
from specter.modelos.pacotes import Pacote, VersaoPacote
from specter.modelos.features import FeaturePacote
from specter.modelos.api_keys import ChaveAPI
from specter.api.auth import dependencia_api_key

router = APIRouter()


class VersaoInfo(BaseModel):
    versao: str
    publicado_em: str | None
    tem_postinstall: bool
    tem_preinstall: bool
    contagem_mantenedores: int


class FeaturesInfo(BaseModel):
    score_risco: float | None
    score_typosquatting: float | None
    tem_github: bool
    estrelas_github: int | None
    provavel_typosquat: bool
    computado_em: str | None


class PacoteDetalhado(BaseModel):
    id: int
    nome: str
    ecossistema: str
    descricao: str | None
    url_repositorio: str | None
    criado_em: str | None
    atualizado_em: str | None
    versoes: list[VersaoInfo]
    features: FeaturesInfo | None


@router.get("/package/{ecossistema}/{nome}", response_model=PacoteDetalhado)
async def obter_pacote(
    ecossistema: str,
    nome: str,
    chave: ChaveAPI = Depends(dependencia_api_key),
):
    """Retorna historico completo de risco de um pacote."""
    sessao = obter_sessao()
    try:
        pacote = sessao.execute(
            select(Pacote).where(
                Pacote.nome == nome,
                Pacote.ecossistema == ecossistema,
            )
        ).scalar_one_or_none()

        if not pacote:
            raise HTTPException(status_code=404, detail="Pacote nao encontrado")

        versoes_db = sessao.execute(
            select(VersaoPacote)
            .where(VersaoPacote.pacote_id == pacote.id)
            .order_by(VersaoPacote.publicado_em.desc())
        ).scalars().all()

        feature_db = sessao.execute(
            select(FeaturePacote)
            .where(FeaturePacote.pacote_id == pacote.id)
            .order_by(FeaturePacote.computado_em.desc())
            .limit(1)
        ).scalar_one_or_none()

        versoes_info = [
            VersaoInfo(
                versao=v.versao,
                publicado_em=v.publicado_em.isoformat() if v.publicado_em else None,
                tem_postinstall=v.tem_postinstall,
                tem_preinstall=v.tem_preinstall,
                contagem_mantenedores=v.contagem_mantenedores,
            )
            for v in versoes_db
        ]

        features_info = None
        if feature_db:
            features_info = FeaturesInfo(
                score_risco=feature_db.score_risco,
                score_typosquatting=feature_db.score_typosquatting,
                tem_github=feature_db.tem_github,
                estrelas_github=feature_db.estrelas_github,
                provavel_typosquat=feature_db.provavel_typosquat,
                computado_em=feature_db.computado_em.isoformat() if feature_db.computado_em else None,
            )

        return PacoteDetalhado(
            id=pacote.id,
            nome=pacote.nome,
            ecossistema=pacote.ecossistema,
            descricao=pacote.descricao,
            url_repositorio=pacote.url_repositorio,
            criado_em=pacote.criado_em.isoformat() if pacote.criado_em else None,
            atualizado_em=pacote.atualizado_em.isoformat() if pacote.atualizado_em else None,
            versoes=versoes_info,
            features=features_info,
        )
    finally:
        sessao.close()
