"""
Worker Celery para computacao de features em batch.

Busca pacotes sem features (ou desatualizados), computa via extrator,
e salva na tabela features_pacote.

Tambem expoe compute_single() para calculo on-demand (usado pela API de scan).
"""

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from specter.celery_app import app
from specter.config import config
from specter.modelos.base import obter_sessao
from specter.modelos.pacotes import Pacote, VersaoPacote
from specter.modelos.features import FeaturePacote
from specter.features.extrator import extrair_features
from specter.features.cliente_github import ClienteGitHub
from specter.utils.logging_config import obter_logger

log = obter_logger("compute_features")

_MAX_WORKERS_GITHUB = 4


@app.task(
    name="specter.features.compute_features.tarefa_computar_features_batch",
    bind=True,
    max_retries=2,
)
def tarefa_computar_features_batch(self, limite: int = 500):
    """
    Computa features para pacotes que ainda nao possuem,
    ou cujo atualizado_em e mais recente que computado_em.
    """
    sessao = obter_sessao()
    try:
        subquery_ja_computados = (
            select(FeaturePacote.pacote_id)
            .correlate(Pacote)
            .scalar_subquery()
        )

        pacotes_pendentes = sessao.execute(
            select(Pacote)
            .where(Pacote.id.notin_(subquery_ja_computados))
            .limit(limite)
        ).scalars().all()

        if not pacotes_pendentes:
            log.info("features_batch_sem_pendentes")
            return {"processados": 0}

        total = 0
        with ClienteGitHub() as gh:
            for pacote in pacotes_pendentes:
                try:
                    _computar_e_salvar(sessao, pacote, gh)
                    total += 1
                    if total % 50 == 0:
                        log.info("features_batch_progresso", processados=total)
                except Exception as e:
                    log.warning(
                        "features_batch_erro_pacote",
                        pacote=pacote.nome,
                        erro=str(e),
                    )
                    sessao.rollback()

        log.info("features_batch_completo", total=total)
        return {"processados": total}

    except Exception as exc:
        sessao.rollback()
        log.error("features_batch_erro", erro=str(exc))
        raise self.retry(exc=exc, countdown=120)
    finally:
        sessao.close()


@app.task(
    name="specter.features.compute_features.tarefa_computar_single",
    bind=True,
    max_retries=2,
)
def tarefa_computar_single(self, nome_pacote: str, ecossistema: str = "npm"):
    """Computa features de um unico pacote (on-demand via API)."""
    return computar_single(nome_pacote, ecossistema)


def computar_single(nome_pacote: str, ecossistema: str = "npm") -> dict | None:
    """
    Computa features de um pacote especifico.
    Retorna o dict de features ou None se pacote nao encontrado.
    """
    sessao = obter_sessao()
    try:
        pacote = sessao.execute(
            select(Pacote).where(
                Pacote.nome == nome_pacote,
                Pacote.ecossistema == ecossistema,
            )
        ).scalar_one_or_none()

        if not pacote:
            log.warning("compute_single_nao_encontrado", pacote=nome_pacote)
            return None

        with ClienteGitHub() as gh:
            features = _computar_e_salvar(sessao, pacote, gh)

        return features

    except Exception as e:
        sessao.rollback()
        log.error("compute_single_erro", pacote=nome_pacote, erro=str(e))
        return None
    finally:
        sessao.close()


def _computar_e_salvar(sessao, pacote: Pacote, gh: ClienteGitHub) -> dict:
    """Computa features de um pacote e persiste no banco."""

    versoes_db = sessao.execute(
        select(VersaoPacote).where(VersaoPacote.pacote_id == pacote.id)
    ).scalars().all()

    versoes_dict = []
    for v in versoes_db:
        versoes_dict.append({
            "versao": v.versao,
            "publicado_em": v.publicado_em.isoformat() if v.publicado_em else None,
            "contagem_mantenedores": v.contagem_mantenedores,
            "tem_postinstall": v.tem_postinstall,
            "tem_preinstall": v.tem_preinstall,
            "scripts": v.scripts or {},
            "dependencias": v.dependencias or {},
            "mantenedores": v.mantenedores or [],
        })

    registro = {
        "nome": pacote.nome,
        "data_criacao": pacote.criado_em.isoformat() if pacote.criado_em else None,
        "url_repositorio": pacote.url_repositorio,
        "descricao": pacote.descricao,
        "versoes": versoes_dict,
    }

    features = extrair_features(registro, cliente_github=gh)

    ultima_versao = None
    if versoes_db:
        ultima_versao = max(versoes_db, key=lambda v: v.publicado_em or datetime.min.replace(tzinfo=timezone.utc))

    stmt = pg_insert(FeaturePacote).values(
        pacote_id=pacote.id,
        versao_id=ultima_versao.id if ultima_versao else None,
        idade_dias=features.get("idade_pacote_dias"),
        dias_desde_ultima_publicacao=features.get("dias_desde_ultima_publicacao"),
        total_versoes=features.get("total_versoes"),
        frequencia_versoes=features.get("frequencia_versoes"),
        pacote_novo=bool(features.get("pacote_novo")),
        contagem_mantenedores=features.get("contagem_mantenedores"),
        mantenedor_unico=bool(features.get("mantenedor_unico")),
        tem_github=bool(features.get("tem_github")),
        estrelas_github=features.get("estrelas_github"),
        idade_github_dias=features.get("idade_github_dias"),
        contribuidores_github=features.get("contribuidores_github"),
        tem_script_postinstall=bool(features.get("tem_script_postinstall")),
        tem_script_preinstall=bool(features.get("tem_script_preinstall")),
        tamanho_script_instalacao=features.get("tamanho_script_instalacao", 0),
        score_typosquatting=features.get("score_typosquatting"),
        distancia_edicao_minima=features.get("distancia_edicao_minima"),
        provavel_typosquat=bool(features.get("provavel_typosquat")),
        computado_em=datetime.now(timezone.utc),
    ).on_conflict_do_nothing()

    sessao.execute(stmt)
    sessao.commit()

    log.debug("features_salvas", pacote=pacote.nome)
    return features
