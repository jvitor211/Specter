"""
Configuracao de logging estruturado para o Specter.
Usa structlog com output JSON + integracao com Celery signals.
"""

import logging
import sys

import structlog
from celery.signals import task_failure, task_postrun, task_prerun

from specter.config import config


def configurar_logging() -> None:
    """Inicializa o structlog com processadores padrao e output JSON."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(config.LOG_LEVEL)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def obter_logger(nome: str) -> structlog.BoundLogger:
    """Retorna um logger nomeado para o modulo."""
    return structlog.get_logger(modulo=nome)


# ---------------------------------------------------------------------------
# Integracao com Celery signals
# ---------------------------------------------------------------------------

_log = structlog.get_logger(modulo="celery_signals")


@task_prerun.connect
def _ao_iniciar_tarefa(sender=None, task_id=None, task=None, **kwargs):
    _log.info(
        "tarefa_iniciada",
        tarefa=sender.name if sender else "desconhecida",
        task_id=task_id,
    )


@task_postrun.connect
def _ao_finalizar_tarefa(
    sender=None, task_id=None, retval=None, state=None, **kwargs
):
    _log.info(
        "tarefa_finalizada",
        tarefa=sender.name if sender else "desconhecida",
        task_id=task_id,
        estado=state,
    )


@task_failure.connect
def _ao_falhar_tarefa(
    sender=None, task_id=None, exception=None, traceback=None, **kwargs
):
    _log.error(
        "tarefa_falhou",
        tarefa=sender.name if sender else "desconhecida",
        task_id=task_id,
        erro=str(exception),
    )
