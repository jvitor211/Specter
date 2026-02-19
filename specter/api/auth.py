"""
Sistema de autenticacao por API key para o Specter.

Formato da key: spk_live_XXXXXXXXXXXXXXXX
Armazenamento: hash SHA256 no banco (nunca em texto plano).

Tiers:
  - free: 500 scans/mes
  - pro: ilimitado
  - enterprise: ilimitado + endpoints extras
"""

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import Header, HTTPException, Request
from sqlalchemy import select

from specter.modelos.base import obter_sessao
from specter.modelos.api_keys import ChaveAPI, LogUso
from specter.utils.logging_config import obter_logger

log = obter_logger("auth")

_LIMITES_TIER = {
    "free": 500,
    "pro": float("inf"),
    "enterprise": float("inf"),
}


def gerar_chave() -> str:
    """Gera uma API key no formato spk_live_XXXXXXXXXXXXXXXX."""
    sufixo = secrets.token_hex(16)
    return f"spk_live_{sufixo}"


def hash_chave(chave: str) -> str:
    """Hash SHA256 da API key para armazenamento seguro."""
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()


def validar_chave(chave: str) -> ChaveAPI | None:
    """Valida uma API key e retorna o registro ou None."""
    h = hash_chave(chave)
    sessao = obter_sessao()
    try:
        registro = sessao.execute(
            select(ChaveAPI).where(ChaveAPI.hash_chave == h)
        ).scalar_one_or_none()

        if registro:
            registro.ultimo_uso_em = datetime.now(timezone.utc)
            sessao.commit()

        return registro
    finally:
        sessao.close()


def verificar_rate_limit(chave_id: int, tier: str) -> bool:
    """Verifica se a chave nao excedeu o limite mensal."""
    limite = _LIMITES_TIER.get(tier, 500)
    if limite == float("inf"):
        return True

    sessao = obter_sessao()
    try:
        registro = sessao.execute(
            select(ChaveAPI).where(ChaveAPI.id == chave_id)
        ).scalar_one_or_none()

        if not registro:
            return False

        return registro.requisicoes_mes < limite
    finally:
        sessao.close()


def registrar_uso(
    chave_id: int, endpoint: str, tempo_resposta_ms: int, pacotes: int = 0
) -> None:
    """Registra uso da API para metricas e billing."""
    sessao = obter_sessao()
    try:
        log_entry = LogUso(
            chave_api_id=chave_id,
            endpoint=endpoint,
            tempo_resposta_ms=tempo_resposta_ms,
            pacotes_escaneados=pacotes,
        )
        sessao.add(log_entry)

        chave = sessao.execute(
            select(ChaveAPI).where(ChaveAPI.id == chave_id)
        ).scalar_one_or_none()
        if chave:
            chave.requisicoes_mes += 1

        sessao.commit()
    except Exception as e:
        sessao.rollback()
        log.warning("registro_uso_erro", erro=str(e))
    finally:
        sessao.close()


async def dependencia_api_key(
    x_specter_key: str = Header(None, alias="X-Specter-Key"),
) -> ChaveAPI:
    """
    Dependencia FastAPI para validacao de API key.
    Usar em rotas protegidas: Depends(dependencia_api_key)
    """
    if not x_specter_key:
        raise HTTPException(
            status_code=401,
            detail="Header X-Specter-Key obrigatorio",
        )

    chave = validar_chave(x_specter_key)
    if not chave:
        raise HTTPException(
            status_code=401,
            detail="API key invalida",
        )

    if not verificar_rate_limit(chave.id, chave.tier):
        raise HTTPException(
            status_code=429,
            detail=f"Limite mensal excedido para tier '{chave.tier}'",
        )

    return chave
