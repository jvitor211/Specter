"""
Rota POST /v1/feedback — reportar falso positivo/negativo.
Dados salvos para retreino futuro do modelo Wings.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from specter.modelos.base import obter_sessao
from specter.modelos.pacotes import Pacote
from specter.modelos.maliciosos import MaliciosoConhecido
from specter.modelos.api_keys import ChaveAPI
from specter.api.auth import dependencia_api_key
from specter.utils.logging_config import obter_logger

log = obter_logger("rota_feedback")

router = APIRouter()


class RequestFeedback(BaseModel):
    package: str
    ecosystem: str = "npm"
    version: str | None = None
    is_false_positive: bool


class ResponseFeedback(BaseModel):
    status: str
    message: str


@router.post("/feedback", response_model=ResponseFeedback)
async def enviar_feedback(
    body: RequestFeedback,
    chave: ChaveAPI = Depends(dependencia_api_key),
):
    """
    Recebe feedback de falso positivo/negativo.
    Falso negativo: insere em maliciosos_conhecidos (source='manual').
    Falso positivo: remove de maliciosos_conhecidos (se existir).
    """
    sessao = obter_sessao()
    try:
        pacote = sessao.execute(
            select(Pacote).where(
                Pacote.nome == body.package,
                Pacote.ecossistema == body.ecosystem,
            )
        ).scalar_one_or_none()

        if not pacote:
            return ResponseFeedback(
                status="ignorado",
                message=f"Pacote '{body.package}' nao encontrado no banco",
            )

        if body.is_false_positive:
            registro = sessao.execute(
                select(MaliciosoConhecido).where(
                    MaliciosoConhecido.pacote_id == pacote.id,
                    MaliciosoConhecido.fonte == "manual",
                )
            ).scalar_one_or_none()

            if registro:
                sessao.delete(registro)
                sessao.commit()

            log.info("feedback_falso_positivo", pacote=body.package)
            return ResponseFeedback(
                status="ok",
                message=f"Falso positivo registrado para '{body.package}'",
            )
        else:
            stmt = pg_insert(MaliciosoConhecido).values(
                pacote_id=pacote.id,
                fonte="manual",
                notas=f"Feedback via API | versao={body.version}",
            ).on_conflict_do_nothing()
            sessao.execute(stmt)
            sessao.commit()

            log.info("feedback_falso_negativo", pacote=body.package)
            return ResponseFeedback(
                status="ok",
                message=f"Pacote '{body.package}' marcado como malicioso (manual)",
            )

    except Exception as e:
        sessao.rollback()
        log.error("feedback_erro", erro=str(e))
        return ResponseFeedback(status="erro", message=str(e)[:200])
    finally:
        sessao.close()
