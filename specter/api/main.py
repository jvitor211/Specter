"""
API REST principal do Specter — FastAPI.

Endpoints:
  POST /v1/scan          — scan de pacotes (ate 50 por request)
  GET  /v1/package/{e}/{n} — historico de risco de um pacote
  GET  /v1/health        — status da API
  POST /v1/feedback      — reportar falso positivo/negativo
  POST /v1/keys/create   — criar API key (sem auth)
  GET  /v1/keys/usage    — uso do mes (com auth)
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from specter.config import config
from specter.utils.logging_config import configurar_logging
from specter.api.rotas.scan import router as scan_router
from specter.api.rotas.pacotes import router as pacotes_router
from specter.api.rotas.feedback import router as feedback_router
from specter.api.rotas.keys import router as keys_router
from specter.api.rotas.stats import router as stats_router
from specter.api.rotas.stripe_billing import router as stripe_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configurar_logging()
    yield


app = FastAPI(
    title="Specter API",
    description="Deteccao de pacotes maliciosos em supply chain npm/PyPI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan_router, prefix="/v1", tags=["scan"])
app.include_router(pacotes_router, prefix="/v1", tags=["pacotes"])
app.include_router(feedback_router, prefix="/v1", tags=["feedback"])
app.include_router(keys_router, prefix="/v1/keys", tags=["keys"])
app.include_router(stats_router, prefix="/v1", tags=["stats"])
app.include_router(stripe_router, prefix="/v1/stripe", tags=["stripe"])


@app.get("/")
async def root():
    """Rota raiz — redireciona para health."""
    return {"service": "specter-api", "docs": "/docs", "health": "/v1/health"}


@app.get("/v1/health")
async def health():
    """Status da API, versao do modelo, ultima atualizacao."""
    modelo_existe = (config.DIR_MODELOS / "wings_v1.joblib").exists()
    return {
        "status": "ok",
        "versao_api": "0.1.0",
        "modelo_carregado": modelo_existe,
        "timestamp": time.time(),
    }
