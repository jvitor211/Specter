"""
Tarefas Celery para ingestao incremental de pacotes npm e PyPI.

Fluxo npm:
  1. tarefa_sincronizar_npm — paginacao via _all_docs, dispatch por pacote
  2. tarefa_processar_pacote — busca detalhes, upsert pacote + versoes
  3. tarefa_processar_versoes — bulk upsert de versoes

Fluxo PyPI:
  1. tarefa_sincronizar_pypi — parse de /simple/, dispatch por pacote
  2. tarefa_processar_pacote_pypi — busca JSON, upsert

OSV:
  1. tarefa_atualizar_osv — download bulk + socket feed
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from specter.celery_app import app
from specter.config import config
from specter.modelos.base import obter_sessao
from specter.modelos.pacotes import Pacote, VersaoPacote
from specter.modelos.etag import RegistroEtag
from specter.ingestao.cliente_npm import ClienteNpm
from specter.ingestao.parser import parsear_pacote_npm
from specter.utils.logging_config import obter_logger

log = obter_logger("tarefas_ingestao")

_ENDPOINT_NPM_ALL_DOCS = "npm/_all_docs"
_ENDPOINT_NPM_ALL = "npm/-/all"


# =============================================================================
# TAREFAS NPM
# =============================================================================


@app.task(name="specter.ingestao.tarefas.tarefa_sincronizar_npm", bind=True)
def tarefa_sincronizar_npm(self):
    """
    Sincroniza o registry npm de forma incremental.
    Usa cursor (startkey) salvo no banco para retomar de onde parou.
    Dispatch tarefa_processar_pacote para cada nome encontrado.
    """
    sessao = obter_sessao()
    try:
        registro = sessao.execute(
            select(RegistroEtag).where(RegistroEtag.endpoint == _ENDPOINT_NPM_ALL_DOCS)
        ).scalar_one_or_none()

        cursor_atual = registro.ultimo_cursor if registro else None
        total_processados = 0

        with ClienteNpm() as cliente:
            while True:
                resultado = cliente.listar_pacotes(startkey=cursor_atual)

                if not resultado.pacotes:
                    log.info("npm_sync_completo", total=total_processados)
                    break

                for pkg in resultado.pacotes:
                    tarefa_processar_pacote.delay(pkg["nome"], "npm")

                total_processados += len(resultado.pacotes)
                cursor_atual = resultado.ultimo_cursor

                if registro is None:
                    registro = RegistroEtag(
                        endpoint=_ENDPOINT_NPM_ALL_DOCS,
                        ultimo_cursor=cursor_atual,
                    )
                    sessao.add(registro)
                else:
                    registro.ultimo_cursor = cursor_atual
                    registro.atualizado_em = datetime.now(timezone.utc)

                sessao.commit()

                if total_processados % config.NPM_LOG_INTERVAL == 0:
                    log.info(
                        "npm_sync_progresso",
                        processados=total_processados,
                        cursor=cursor_atual,
                    )

        return {"total_processados": total_processados, "cursor_final": cursor_atual}

    except Exception as exc:
        sessao.rollback()
        log.error("npm_sync_erro", erro=str(exc))
        raise self.retry(exc=exc, countdown=60, max_retries=3)
    finally:
        sessao.close()


@app.task(
    name="specter.ingestao.tarefas.tarefa_processar_pacote",
    bind=True,
    rate_limit="80/m",
    max_retries=3,
    default_retry_delay=30,
)
def tarefa_processar_pacote(self, nome_pacote: str, ecossistema: str = "npm"):
    """
    Busca detalhes de um pacote no registry e faz upsert no banco.
    Dispatch tarefa_processar_versoes com os dados das versoes.
    """
    sessao = obter_sessao()
    try:
        with ClienteNpm() as cliente:
            dados_brutos = cliente.obter_pacote(nome_pacote)

        if dados_brutos is None:
            log.warning("pacote_ignorado_404", pacote=nome_pacote)
            return {"status": "ignorado", "motivo": "404"}

        if ecossistema == "npm":
            dados = parsear_pacote_npm(dados_brutos)
        else:
            from specter.ingestao.parser import parsear_pacote_pypi
            dados = parsear_pacote_pypi(dados_brutos)

        info = dados["info_pacote"]

        stmt = pg_insert(Pacote).values(
            nome=info["nome"],
            ecossistema=info["ecossistema"],
            descricao=info.get("descricao"),
            url_repositorio=info.get("url_repositorio"),
            criado_em=info.get("criado_em") or datetime.now(timezone.utc),
            atualizado_em=info.get("atualizado_em") or datetime.now(timezone.utc),
        ).on_conflict_do_update(
            constraint="uq_pacotes_nome_eco",
            set_={
                "descricao": info.get("descricao"),
                "url_repositorio": info.get("url_repositorio"),
                "atualizado_em": datetime.now(timezone.utc),
            },
        ).returning(Pacote.id)

        resultado = sessao.execute(stmt)
        pacote_id = resultado.scalar_one()
        sessao.commit()

        if dados["versoes"]:
            tarefa_processar_versoes.delay(pacote_id, dados["versoes"])

        log.info(
            "pacote_processado",
            pacote=nome_pacote,
            pacote_id=pacote_id,
            versoes=len(dados["versoes"]),
        )
        return {"pacote_id": pacote_id, "versoes": len(dados["versoes"])}

    except Exception as exc:
        sessao.rollback()
        log.error("pacote_erro", pacote=nome_pacote, erro=str(exc))
        raise self.retry(exc=exc)
    finally:
        sessao.close()


@app.task(
    name="specter.ingestao.tarefas.tarefa_processar_versoes",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
)
def tarefa_processar_versoes(self, pacote_id: int, versoes: list[dict]):
    """
    Bulk upsert de versoes de um pacote.
    Detecta scripts postinstall/preinstall automaticamente.
    """
    sessao = obter_sessao()
    try:
        for v in versoes:
            stmt = pg_insert(VersaoPacote).values(
                pacote_id=pacote_id,
                versao=v["versao"],
                publicado_em=v.get("publicado_em"),
                contagem_mantenedores=v.get("contagem_mantenedores", 0),
                tem_postinstall=v.get("tem_postinstall", False),
                tem_preinstall=v.get("tem_preinstall", False),
                descricao=v.get("descricao"),
                scripts=v.get("scripts", {}),
                dependencias=v.get("dependencias", {}),
                mantenedores=v.get("mantenedores", []),
                metadados=v.get("metadados", {}),
            ).on_conflict_do_update(
                constraint="uq_versao_pacote",
                set_={
                    "publicado_em": v.get("publicado_em"),
                    "contagem_mantenedores": v.get("contagem_mantenedores", 0),
                    "tem_postinstall": v.get("tem_postinstall", False),
                    "tem_preinstall": v.get("tem_preinstall", False),
                    "scripts": v.get("scripts", {}),
                    "dependencias": v.get("dependencias", {}),
                    "mantenedores": v.get("mantenedores", []),
                    "metadados": v.get("metadados", {}),
                },
            )
            sessao.execute(stmt)

        sessao.commit()
        log.info("versoes_processadas", pacote_id=pacote_id, total=len(versoes))
        return {"pacote_id": pacote_id, "versoes_inseridas": len(versoes)}

    except Exception as exc:
        sessao.rollback()
        log.error("versoes_erro", pacote_id=pacote_id, erro=str(exc))
        raise self.retry(exc=exc)
    finally:
        sessao.close()


# =============================================================================
# TAREFAS PyPI
# =============================================================================


@app.task(name="specter.ingestao.tarefas.tarefa_sincronizar_pypi", bind=True)
def tarefa_sincronizar_pypi(self):
    """
    Sincroniza o registry PyPI.
    Parse de /simple/ (HTML), dispatch por pacote.
    """
    from specter.ingestao.cliente_pypi import ClientePyPI
    from specter.ingestao.parser import parsear_pacote_pypi

    sessao = obter_sessao()
    try:
        with ClientePyPI() as cliente:
            nomes = cliente.listar_todos_pacotes()

        total = 0
        for nome in nomes:
            tarefa_processar_pacote_pypi.delay(nome)
            total += 1
            if total % config.NPM_LOG_INTERVAL == 0:
                log.info("pypi_sync_progresso", processados=total)

        log.info("pypi_sync_completo", total_dispatch=total)
        return {"total_dispatch": total}

    except Exception as exc:
        log.error("pypi_sync_erro", erro=str(exc))
        raise self.retry(exc=exc, countdown=120, max_retries=3)
    finally:
        sessao.close()


@app.task(
    name="specter.ingestao.tarefas.tarefa_processar_pacote_pypi",
    bind=True,
    rate_limit="80/m",
    max_retries=3,
    default_retry_delay=30,
)
def tarefa_processar_pacote_pypi(self, nome_pacote: str):
    """Busca detalhes de um pacote PyPI e faz upsert no banco."""
    from specter.ingestao.cliente_pypi import ClientePyPI
    from specter.ingestao.parser import parsear_pacote_pypi

    sessao = obter_sessao()
    try:
        with ClientePyPI() as cliente:
            dados_brutos = cliente.obter_pacote(nome_pacote)

        if dados_brutos is None:
            return {"status": "ignorado", "motivo": "404"}

        dados = parsear_pacote_pypi(dados_brutos)
        info = dados["info_pacote"]

        from datetime import datetime, timezone
        stmt = pg_insert(Pacote).values(
            nome=info["nome"],
            ecossistema="pypi",
            descricao=info.get("descricao"),
            url_repositorio=info.get("url_repositorio"),
            criado_em=info.get("criado_em") or datetime.now(timezone.utc),
            atualizado_em=info.get("atualizado_em") or datetime.now(timezone.utc),
        ).on_conflict_do_update(
            constraint="uq_pacotes_nome_eco",
            set_={
                "descricao": info.get("descricao"),
                "url_repositorio": info.get("url_repositorio"),
                "atualizado_em": datetime.now(timezone.utc),
            },
        ).returning(Pacote.id)

        resultado = sessao.execute(stmt)
        pacote_id = resultado.scalar_one()
        sessao.commit()

        if dados["versoes"]:
            tarefa_processar_versoes.delay(pacote_id, dados["versoes"])

        return {"pacote_id": pacote_id, "versoes": len(dados["versoes"])}

    except Exception as exc:
        sessao.rollback()
        log.error("pypi_pacote_erro", pacote=nome_pacote, erro=str(exc))
        raise self.retry(exc=exc)
    finally:
        sessao.close()


# =============================================================================
# TAREFAS OSV
# =============================================================================


@app.task(name="specter.ingestao.tarefas.tarefa_atualizar_osv", bind=True)
def tarefa_atualizar_osv(self):
    """
    Atualiza base de maliciosos conhecidos.
    Download bulk OSV + processamento.
    """
    from specter.ingestao.ingest_osv import baixar_e_processar_osv

    try:
        stats = baixar_e_processar_osv()
        return stats
    except Exception as exc:
        log.error("osv_update_erro", erro=str(exc))
        raise self.retry(exc=exc, countdown=300, max_retries=2)
