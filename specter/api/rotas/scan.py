"""
Rota POST /v1/scan — scan de pacotes em batch.
Maximo 50 pacotes por request. Cache Redis (TTL 1h).
Target response time: <200ms (cache), <2s (sem cache).
"""

import json
import time

import redis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from specter.config import config
from specter.modelos.api_keys import ChaveAPI
from specter.api.auth import dependencia_api_key, registrar_uso
from specter.features.compute_features import computar_single
from specter.ml.llm_analyzer import score_combinado
from specter.utils.logging_config import obter_logger

log = obter_logger("rota_scan")

router = APIRouter()

_CACHE_TTL = 3600
_MAX_PACOTES = 50


class PacoteScan(BaseModel):
    name: str
    version: str | None = None
    ecosystem: str = "npm"


class RequestScan(BaseModel):
    packages: list[PacoteScan] = Field(..., max_length=_MAX_PACOTES)


class ResultadoPacote(BaseModel):
    name: str
    ecosystem: str
    version: str | None
    score: float
    verdict: str
    top_reasons: list[str]
    recommendation: str


class ResponseScan(BaseModel):
    session_id: str
    packages: list[ResultadoPacote]
    total_scanned: int
    total_flagged: int
    response_time_ms: int


def _obter_redis() -> redis.Redis | None:
    try:
        r = redis.from_url(config.REDIS_URL, decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None


def _chave_cache(nome: str, eco: str, versao: str | None) -> str:
    return f"specter:scan:{eco}:{nome}:{versao or 'latest'}"


def _recomendacao(verdict: str) -> str:
    if verdict == "blocked":
        return "NAO USE este pacote. Risco alto de malware detectado."
    elif verdict == "review":
        return "Revise manualmente antes de usar. Sinais suspeitos encontrados."
    return "Pacote considerado seguro pelo Specter."


@router.post("/scan", response_model=ResponseScan)
async def scan_pacotes(
    body: RequestScan,
    chave: ChaveAPI = Depends(dependencia_api_key),
):
    """
    Escaneia ate 50 pacotes por request.
    Para cada: busca cache -> computa features -> roda Wings -> LLM se borderline.
    """
    inicio = time.monotonic()
    r = _obter_redis()

    resultados = []
    flagged = 0

    for pkg in body.packages:
        cache_key = _chave_cache(pkg.name, pkg.ecosystem, pkg.version)

        if r:
            cached = r.get(cache_key)
            if cached:
                resultado = json.loads(cached)
                resultados.append(ResultadoPacote(**resultado))
                if resultado["verdict"] != "safe":
                    flagged += 1
                continue

        try:
            features = computar_single(pkg.name, pkg.ecosystem)
            if not features:
                resultados.append(ResultadoPacote(
                    name=pkg.name,
                    ecosystem=pkg.ecosystem,
                    version=pkg.version,
                    score=0.0,
                    verdict="unknown",
                    top_reasons=["Pacote nao encontrado no banco"],
                    recommendation="Pacote desconhecido. Verifique manualmente.",
                ))
                continue

            from specter.ml.train_model import predict
            try:
                predicao = predict(features)
            except FileNotFoundError:
                predicao = {
                    "score": 0.0,
                    "verdict": "unknown",
                    "top_reasons": ["Modelo Wings nao treinado"],
                    "threshold": 0.5,
                }

            wings_score = predicao["score"]

            if 0.3 <= wings_score <= 0.7:
                try:
                    dados_pkg = {
                        "nome": pkg.name,
                        "ecossistema": pkg.ecosystem,
                        **features,
                    }
                    combinado = score_combinado(wings_score, dados_pkg)
                    wings_score = combinado["score_final"]
                    if combinado["llm_result"].get("reasons"):
                        predicao["top_reasons"].extend(
                            combinado["llm_result"]["reasons"][:2]
                        )
                except Exception:
                    pass

            if wings_score >= 0.7:
                verdict = "blocked"
            elif wings_score >= predicao.get("threshold", 0.5):
                verdict = "review"
            else:
                verdict = "safe"

            resultado_dict = {
                "name": pkg.name,
                "ecosystem": pkg.ecosystem,
                "version": pkg.version,
                "score": round(wings_score, 4),
                "verdict": verdict,
                "top_reasons": predicao.get("top_reasons", [])[:3],
                "recommendation": _recomendacao(verdict),
            }

            if r:
                r.setex(cache_key, _CACHE_TTL, json.dumps(resultado_dict))

            resultados.append(ResultadoPacote(**resultado_dict))
            if verdict != "safe":
                flagged += 1

        except Exception as e:
            log.error("scan_pacote_erro", pacote=pkg.name, erro=str(e))
            resultados.append(ResultadoPacote(
                name=pkg.name,
                ecosystem=pkg.ecosystem,
                version=pkg.version,
                score=0.0,
                verdict="error",
                top_reasons=[f"Erro interno: {str(e)[:100]}"],
                recommendation="Erro ao processar. Tente novamente.",
            ))

    elapsed_ms = int((time.monotonic() - inicio) * 1000)

    registrar_uso(
        chave_id=chave.id,
        endpoint="/v1/scan",
        tempo_resposta_ms=elapsed_ms,
        pacotes=len(body.packages),
    )

    import uuid
    return ResponseScan(
        session_id=str(uuid.uuid4()),
        packages=resultados,
        total_scanned=len(resultados),
        total_flagged=flagged,
        response_time_ms=elapsed_ms,
    )
