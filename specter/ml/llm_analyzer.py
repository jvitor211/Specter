"""
Analise semantica de pacotes borderline via LLM (Claude ou GPT).

Chamado quando o score do Wings esta entre 0.3 e 0.7 (zona de incerteza).
O LLM analisa README, install scripts e metadata para dar um veredito.

Score combinado: 0.7 * wings_score + 0.3 * llm_confidence

Cache: Redis com TTL de 24h para evitar re-analise.
Custo estimado: ~$0.002 por analise.
"""

import json
from typing import Any

import redis
from pydantic import BaseModel, Field

from specter.config import config
from specter.utils.logging_config import obter_logger

log = obter_logger("llm_analyzer")

_CACHE_TTL = 86400  # 24 horas
_CACHE_PREFIX = "specter:llm:"

_PROMPT_SISTEMA = """Voce e um especialista em seguranca de supply chain de software.
Analise o pacote fornecido e responda APENAS em JSON valido com o formato:
{
  "is_suspicious": bool,
  "confidence": float (0-1),
  "reasons": ["string", ...] (maximo 3),
  "verdict": "safe" | "suspicious" | "malicious"
}

Sinais de risco:
- Nomes similares a pacotes populares (typosquatting)
- Install scripts com acesso a rede, download de binarios
- Leitura de variaveis de ambiente sensiveis (API keys, tokens)
- Acesso a ~/.ssh, ~/.aws, ~/.npmrc ou similar
- Exfiltracao de dados para URLs externas
- Pacote muito novo com poucos mantenedores
- Descricao vaga ou copiada de outro pacote"""


class ResultadoLLM(BaseModel):
    """Resultado validado da analise LLM."""

    is_suspicious: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(max_length=3)
    verdict: str = Field(pattern="^(safe|suspicious|malicious)$")


def _obter_redis() -> redis.Redis | None:
    try:
        r = redis.from_url(config.REDIS_URL, decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None


def _montar_prompt_pacote(dados: dict) -> str:
    """Monta o prompt de analise com os dados do pacote."""
    nome = dados.get("nome", "desconhecido")
    ecossistema = dados.get("ecossistema", "npm")
    descricao = (dados.get("descricao", "") or "")[:500]
    scripts = dados.get("scripts", {})
    dependencias = dados.get("dependencias", {})
    mantenedores = dados.get("mantenedores", [])
    url_repo = dados.get("url_repositorio", "")
    idade_dias = dados.get("idade_pacote_dias", "N/A")

    install_script = ""
    for chave in ["postinstall", "preinstall", "install"]:
        if chave in scripts:
            install_script += f"\n{chave}: {str(scripts[chave])[:300]}"

    deps_str = ", ".join(list(dependencias.keys())[:20]) if dependencias else "nenhuma"
    manut_str = ", ".join(
        [m.get("name", str(m)) if isinstance(m, dict) else str(m) for m in mantenedores[:5]]
    ) if mantenedores else "desconhecido"

    return f"""Pacote: {nome} ({ecossistema})
Descricao: {descricao}
Idade: {idade_dias} dias
Mantenedores: {manut_str}
Repositorio: {url_repo or 'nenhum'}
Dependencias: {deps_str}
Install scripts: {install_script or 'nenhum'}"""


def _chamar_anthropic(prompt: str) -> dict:
    """Chama Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=_PROMPT_SISTEMA,
        messages=[{"role": "user", "content": prompt}],
    )
    texto = response.content[0].text
    return json.loads(texto)


def _chamar_openai(prompt: str) -> dict:
    """Chama OpenAI API."""
    import openai

    client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=500,
        messages=[
            {"role": "system", "content": _PROMPT_SISTEMA},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    texto = response.choices[0].message.content
    return json.loads(texto)


def analisar_pacote(dados_pacote: dict) -> dict:
    """
    Analisa um pacote via LLM.

    Parametros:
      dados_pacote: dict com campos do pacote (nome, descricao, scripts, etc.)

    Retorna:
      dict com is_suspicious, confidence, reasons, verdict
    """
    nome = dados_pacote.get("nome", "")
    eco = dados_pacote.get("ecossistema", "npm")
    chave_cache = f"{_CACHE_PREFIX}{eco}:{nome}"

    r = _obter_redis()
    if r:
        cached = r.get(chave_cache)
        if cached:
            log.debug("llm_cache_hit", pacote=nome)
            return json.loads(cached)

    prompt = _montar_prompt_pacote(dados_pacote)

    try:
        if config.LLM_PROVIDER == "anthropic" and config.ANTHROPIC_API_KEY:
            resultado_raw = _chamar_anthropic(prompt)
        elif config.LLM_PROVIDER == "openai" and config.OPENAI_API_KEY:
            resultado_raw = _chamar_openai(prompt)
        else:
            log.warning("llm_sem_provider_configurado")
            return {
                "is_suspicious": False,
                "confidence": 0.0,
                "reasons": ["LLM nao configurado"],
                "verdict": "safe",
            }

        resultado = ResultadoLLM(**resultado_raw)
        resultado_dict = resultado.model_dump()

        if r:
            r.setex(chave_cache, _CACHE_TTL, json.dumps(resultado_dict))

        log.info(
            "llm_analise_completa",
            pacote=nome,
            verdict=resultado.verdict,
            confidence=resultado.confidence,
        )
        return resultado_dict

    except Exception as e:
        log.error("llm_erro", pacote=nome, erro=str(e))
        return {
            "is_suspicious": False,
            "confidence": 0.0,
            "reasons": [f"Erro LLM: {str(e)[:100]}"],
            "verdict": "safe",
        }


def score_combinado(wings_score: float, dados_pacote: dict) -> dict:
    """
    Combina score do Wings com analise LLM para pacotes borderline.

    Chamado apenas quando 0.3 <= wings_score <= 0.7.

    Retorna:
      {"score_final": float, "wings_score": float, "llm_result": dict}
    """
    llm_result = analisar_pacote(dados_pacote)
    llm_confidence = llm_result.get("confidence", 0.0)

    if llm_result.get("is_suspicious"):
        score_final = 0.7 * wings_score + 0.3 * llm_confidence
    else:
        score_final = 0.7 * wings_score + 0.3 * (1.0 - llm_confidence) * 0.3

    score_final = round(min(max(score_final, 0.0), 1.0), 4)

    return {
        "score_final": score_final,
        "wings_score": wings_score,
        "llm_result": llm_result,
    }
