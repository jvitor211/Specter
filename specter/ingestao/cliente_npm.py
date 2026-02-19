"""
Cliente HTTP para o npm Registry com rate limiting e retry automatico.

Endpoints utilizados:
  - replicate.npmjs.com/_all_docs  — listagem incremental (paginada por startkey)
  - registry.npmjs.org/{nome}      — detalhes completos de um pacote

Rate limit: 80 req/min (token bucket).
Retry: backoff exponencial via tenacity (5 tentativas).
"""

import time
import threading
from dataclasses import dataclass, field

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from specter.config import config
from specter.utils.logging_config import obter_logger

log = obter_logger("cliente_npm")

_URL_BASE_REPLICATE = "https://replicate.npmjs.com"
_URL_BASE_REGISTRY = "https://registry.npmjs.org"


@dataclass
class _TokenBucket:
    """Rate limiter simples baseado em token bucket."""

    capacidade: int = 80
    tokens: float = field(init=False)
    ultimo_reabastecimento: float = field(init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self):
        self.tokens = float(self.capacidade)
        self.ultimo_reabastecimento = time.monotonic()

    def aguardar(self) -> None:
        """Bloqueia ate que um token esteja disponivel."""
        with self._lock:
            agora = time.monotonic()
            decorrido = agora - self.ultimo_reabastecimento
            self.tokens = min(
                self.capacidade, self.tokens + decorrido * (self.capacidade / 60.0)
            )
            self.ultimo_reabastecimento = agora

            if self.tokens < 1.0:
                espera = (1.0 - self.tokens) / (self.capacidade / 60.0)
                log.debug("rate_limit_aguardando", espera_seg=round(espera, 2))
                time.sleep(espera)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


@dataclass
class RespostaListagem:
    """Resultado de uma listagem incremental do registry."""

    pacotes: list[dict]
    total_linhas: int
    ultimo_cursor: str | None
    offset: int


class ClienteNpm:
    """
    Cliente para o npm registry com connection pooling,
    rate limiting e retry automatico.
    """

    def __init__(self):
        self._rate_limiter = _TokenBucket(capacidade=config.NPM_RATE_LIMIT)
        self._client = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )

    def fechar(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.fechar()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        before_sleep=lambda info: obter_logger("cliente_npm").warning(
            "retry_npm",
            tentativa=info.attempt_number,
            espera=round(info.idle_for, 1),
        ),
    )
    def listar_pacotes(
        self,
        startkey: str | None = None,
        limite: int | None = None,
    ) -> RespostaListagem:
        """
        Busca lista de pacotes via _all_docs (paginado).
        Retorna batch de IDs e o cursor para proxima pagina.
        """
        self._rate_limiter.aguardar()

        params: dict = {"limit": limite or config.NPM_BATCH_SIZE}
        if startkey:
            params["startkey"] = f'"{startkey}"'
            params["skip"] = 1

        resp = self._client.get(f"{_URL_BASE_REPLICATE}/_all_docs", params=params)
        resp.raise_for_status()
        dados = resp.json()

        linhas = dados.get("rows", [])
        nomes = [r["id"] for r in linhas if not r["id"].startswith("_")]

        ultimo = linhas[-1]["id"] if linhas else None

        log.info(
            "listagem_npm",
            pacotes_retornados=len(nomes),
            total_linhas=dados.get("total_rows", 0),
            cursor=ultimo,
        )

        return RespostaListagem(
            pacotes=[{"nome": n} for n in nomes],
            total_linhas=dados.get("total_rows", 0),
            ultimo_cursor=ultimo,
            offset=dados.get("offset", 0),
        )

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        before_sleep=lambda info: obter_logger("cliente_npm").warning(
            "retry_npm_pacote",
            tentativa=info.attempt_number,
            espera=round(info.idle_for, 1),
        ),
    )
    def obter_pacote(self, nome: str) -> dict | None:
        """
        Busca detalhes completos de um pacote no registry.
        Retorna None se 404.
        """
        self._rate_limiter.aguardar()

        try:
            resp = self._client.get(f"{_URL_BASE_REGISTRY}/{nome}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                log.warning("pacote_nao_encontrado", pacote=nome)
                return None
            raise

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
    )
    def obter_todos_com_etag(self, etag_anterior: str | None = None) -> tuple[dict | None, str | None]:
        """
        Endpoint /-/all com suporte a ETag para download incremental.
        Retorna (dados, novo_etag) ou (None, etag_anterior) se 304.
        """
        self._rate_limiter.aguardar()

        headers = {}
        if etag_anterior:
            headers["If-None-Match"] = etag_anterior

        resp = self._client.get(f"{_URL_BASE_REGISTRY}/-/all", headers=headers)

        if resp.status_code == 304:
            log.info("npm_sem_alteracoes", etag=etag_anterior)
            return None, etag_anterior

        resp.raise_for_status()
        novo_etag = resp.headers.get("ETag")
        return resp.json(), novo_etag
