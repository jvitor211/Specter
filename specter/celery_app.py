"""
Configuracao da aplicacao Celery com Redis como broker.
Inclui beat schedule para tarefas periodicas.
"""

from celery import Celery
from celery.schedules import crontab

from specter.config import config
from specter.utils.logging_config import configurar_logging

configurar_logging()

app = Celery(
    "specter",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_default_queue="specter",
    worker_max_tasks_per_child=200,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

app.conf.beat_schedule = {
    # Fase 1.2 — Sincronizar registry npm a cada 6 horas
    "sincronizar-npm-6h": {
        "task": "specter.ingestao.tarefas.tarefa_sincronizar_npm",
        "schedule": crontab(minute=0, hour="*/6"),
        "args": (),
    },
    # Fase 1.3 — Sincronizar registry PyPI a cada 6 horas (offset de 3h)
    "sincronizar-pypi-6h": {
        "task": "specter.ingestao.tarefas.tarefa_sincronizar_pypi",
        "schedule": crontab(minute=0, hour="3,9,15,21"),
        "args": (),
    },
    # Fase 1.4 — Atualizar base de maliciosos conhecidos (1x/dia)
    "atualizar-osv-diario": {
        "task": "specter.ingestao.tarefas.tarefa_atualizar_osv",
        "schedule": crontab(minute=30, hour=2),
        "args": (),
    },
    # Fase 2.2 — Computar features em batch a cada 2 horas
    "computar-features-2h": {
        "task": "specter.features.compute_features.tarefa_computar_features_batch",
        "schedule": crontab(minute=15, hour="*/2"),
        "args": (),
    },
}

app.autodiscover_tasks(["specter.ingestao", "specter.features"])

# Import explicito para garantir registro das tasks
import specter.ingestao.tarefas  # noqa: F401, E402
import specter.features.compute_features  # noqa: F401, E402
