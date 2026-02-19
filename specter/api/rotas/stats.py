"""
Rota GET /v1/stats — estatisticas publicas (sem auth) para o dashboard.
Retorna total pacotes, scans do mes, distribuicao de risco, ultimos scans, scans/dia.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import Session

from specter.config import config
from specter.modelos.pacotes import Pacote
from specter.modelos.features import FeaturePacote
from specter.modelos.scan import RequisicaoScan
from specter.utils.logging_config import obter_logger

log = obter_logger("rota_stats")

router = APIRouter()

_engine = create_engine(config.POSTGRES_URL, pool_pre_ping=True)


@router.get("/stats")
def obter_stats():
    """Estatisticas agregadas do Specter para o dashboard."""
    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_30d = agora - timedelta(days=30)

    with Session(_engine) as sess:
        total_pacotes = sess.query(func.count(Pacote.id)).scalar() or 0

        total_scans_mes = (
            sess.query(func.count(RequisicaoScan.id))
            .filter(RequisicaoScan.criado_em >= inicio_mes)
            .scalar()
            or 0
        )

        total_sinalizados = (
            sess.query(func.count(RequisicaoScan.id))
            .filter(
                RequisicaoScan.criado_em >= inicio_mes,
                RequisicaoScan.sinalizado == True,
            )
            .scalar()
            or 0
        )

        dist_safe = (
            sess.query(func.count(FeaturePacote.id))
            .filter(FeaturePacote.score_risco != None, FeaturePacote.score_risco < 0.3)
            .scalar()
            or 0
        )
        dist_review = (
            sess.query(func.count(FeaturePacote.id))
            .filter(
                FeaturePacote.score_risco != None,
                FeaturePacote.score_risco >= 0.3,
                FeaturePacote.score_risco < 0.7,
            )
            .scalar()
            or 0
        )
        dist_blocked = (
            sess.query(func.count(FeaturePacote.id))
            .filter(FeaturePacote.score_risco != None, FeaturePacote.score_risco >= 0.7)
            .scalar()
            or 0
        )

        ultimos_scans_raw = (
            sess.query(RequisicaoScan)
            .order_by(RequisicaoScan.criado_em.desc())
            .limit(10)
            .all()
        )

        scans_por_dia_raw = (
            sess.query(
                func.date(RequisicaoScan.criado_em).label("dia"),
                func.count(RequisicaoScan.id).label("total"),
                func.sum(
                    func.cast(RequisicaoScan.sinalizado, Integer)
                ).label("flagged"),
            )
            .filter(RequisicaoScan.criado_em >= inicio_30d)
            .group_by(func.date(RequisicaoScan.criado_em))
            .order_by(func.date(RequisicaoScan.criado_em))
            .all()
        )

    ultimos_scans = []
    for s in ultimos_scans_raw:
        score = s.score_risco or 0.0
        if score >= 0.7:
            verdict = "blocked"
        elif score >= 0.3:
            verdict = "review"
        else:
            verdict = "safe"

        ultimos_scans.append({
            "pacote": s.nome_pacote,
            "ecossistema": s.ecossistema,
            "score": round(score, 4),
            "verdict": verdict,
            "criado_em": s.criado_em.isoformat() if s.criado_em else None,
        })

    scans_por_dia = [
        {
            "dia": str(row.dia),
            "scans": row.total or 0,
            "flagged": row.flagged or 0,
        }
        for row in scans_por_dia_raw
    ]

    total_com_score = dist_safe + dist_review + dist_blocked
    taxa_seguranca = round((dist_safe / total_com_score) * 100, 1) if total_com_score > 0 else 0.0

    return {
        "total_pacotes": total_pacotes,
        "total_scans_mes": total_scans_mes,
        "total_sinalizados": total_sinalizados,
        "taxa_seguranca": taxa_seguranca,
        "distribuicao": [
            {"name": "Seguro", "value": dist_safe, "cor": "#22c55e"},
            {"name": "Revisar", "value": dist_review, "cor": "#f59e0b"},
            {"name": "Bloqueado", "value": dist_blocked, "cor": "#ff2d4a"},
        ],
        "ultimos_scans": ultimos_scans,
        "scans_por_dia": scans_por_dia,
    }
