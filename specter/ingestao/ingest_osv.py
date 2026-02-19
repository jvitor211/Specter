"""
Ingestao de dados de ameacas conhecidas:
  1. OSV Database (Google) — download bulk + filtro npm/PyPI
  2. Socket.dev public feed — pacotes com score baixo

Popula a tabela maliciosos_conhecidos como ground truth para o modelo ML.
Roda 1x/dia via Celery beat.
"""

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from specter.modelos.base import obter_sessao
from specter.modelos.pacotes import Pacote
from specter.modelos.maliciosos import MaliciosoConhecido
from specter.modelos.etag import RegistroEtag
from specter.utils.logging_config import obter_logger

log = obter_logger("ingest_osv")

_URL_OSV_BULK = "https://osv-vulnerabilities.storage.googleapis.com"
_ECOSSISTEMAS_ALVO = {"npm", "PyPI"}
_ENDPOINT_OSV = "osv/all.zip"


def baixar_e_processar_osv() -> dict:
    """
    Faz download do OSV bulk ZIP, filtra npm/PyPI,
    e insere pacotes afetados em maliciosos_conhecidos.

    Usa ETag para evitar re-download se nao houve alteracao.
    """
    sessao = obter_sessao()
    stats = {"baixados": 0, "inseridos": 0, "ignorados": 0, "erro": 0}

    try:
        registro = sessao.execute(
            select(RegistroEtag).where(RegistroEtag.endpoint == _ENDPOINT_OSV)
        ).scalar_one_or_none()

        etag_anterior = registro.etag if registro else None

        headers = {}
        if etag_anterior:
            headers["If-None-Match"] = etag_anterior

        ecosistemas_urls = []
        for eco in _ECOSSISTEMAS_ALVO:
            ecosistemas_urls.append(f"{_URL_OSV_BULK}/{eco}/all.zip")

        with httpx.Client(timeout=120.0) as client:
            for eco, url in zip(_ECOSSISTEMAS_ALVO, ecosistemas_urls):
                try:
                    resp = client.get(url, headers=headers)

                    if resp.status_code == 304:
                        log.info("osv_sem_alteracoes", ecossistema=eco)
                        continue

                    resp.raise_for_status()
                    stats["baixados"] += 1

                    zip_bytes = io.BytesIO(resp.content)
                    with zipfile.ZipFile(zip_bytes) as zf:
                        for nome_arquivo in zf.namelist():
                            if not nome_arquivo.endswith(".json"):
                                continue
                            try:
                                dados = json.loads(zf.read(nome_arquivo))
                                _processar_vulnerabilidade_osv(
                                    sessao, dados, eco.lower(), stats
                                )
                            except (json.JSONDecodeError, KeyError) as e:
                                stats["erro"] += 1
                                log.debug("osv_json_erro", arquivo=nome_arquivo, erro=str(e))

                    novo_etag = resp.headers.get("ETag")
                    if novo_etag:
                        if registro is None:
                            registro = RegistroEtag(
                                endpoint=_ENDPOINT_OSV, etag=novo_etag
                            )
                            sessao.add(registro)
                        else:
                            registro.etag = novo_etag
                            registro.atualizado_em = datetime.now(timezone.utc)

                except Exception as e:
                    log.error("osv_download_erro", ecossistema=eco, erro=str(e))
                    stats["erro"] += 1

        sessao.commit()
        log.info("osv_ingestao_completa", **stats)
        return stats

    except Exception as e:
        sessao.rollback()
        log.error("osv_erro_geral", erro=str(e))
        raise
    finally:
        sessao.close()


def _processar_vulnerabilidade_osv(
    sessao, dados: dict, ecossistema: str, stats: dict
) -> None:
    """Processa uma vulnerabilidade do OSV e insere pacotes afetados."""
    afetados = dados.get("affected", [])
    for af in afetados:
        pkg = af.get("package", {})
        eco = pkg.get("ecosystem", "").lower()

        if eco not in {"npm", "pypi"}:
            continue

        nome = pkg.get("name", "")
        if not nome:
            continue

        pacote = sessao.execute(
            select(Pacote).where(
                Pacote.nome == nome,
                Pacote.ecossistema == eco,
            )
        ).scalar_one_or_none()

        if not pacote:
            stmt_pacote = pg_insert(Pacote).values(
                nome=nome, ecossistema=eco
            ).on_conflict_do_nothing().returning(Pacote.id)
            result = sessao.execute(stmt_pacote)
            pacote_id = result.scalar()
            if not pacote_id:
                pacote = sessao.execute(
                    select(Pacote).where(
                        Pacote.nome == nome, Pacote.ecossistema == eco
                    )
                ).scalar_one_or_none()
                pacote_id = pacote.id if pacote else None
        else:
            pacote_id = pacote.id

        if not pacote_id:
            stats["ignorados"] += 1
            continue

        severidade = ""
        for s in dados.get("severity", []):
            severidade += f"{s.get('type', '')}: {s.get('score', '')} "

        stmt = pg_insert(MaliciosoConhecido).values(
            pacote_id=pacote_id,
            fonte="osv",
            notas=f"OSV-{dados.get('id', 'N/A')} | {severidade.strip()}",
        ).on_conflict_do_nothing()

        sessao.execute(stmt)
        stats["inseridos"] += 1
