FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY specter/ specter/
COPY migrations/ migrations/
COPY alembic.ini .
COPY init.sql .

RUN mkdir -p data models

EXPOSE 8000

# -------------------------------------------------------------------
# Target: api (default) — FastAPI server
# -------------------------------------------------------------------
FROM base AS api
CMD ["uvicorn", "specter.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# -------------------------------------------------------------------
# Target: worker — Celery worker
# -------------------------------------------------------------------
FROM base AS worker
CMD ["celery", "-A", "specter.celery_app", "worker", "--loglevel=info", "-Q", "specter", "--pool=solo", "--concurrency=4"]

# -------------------------------------------------------------------
# Target: beat — Celery beat scheduler
# -------------------------------------------------------------------
FROM base AS beat
CMD ["celery", "-A", "specter.celery_app", "beat", "--loglevel=info"]
