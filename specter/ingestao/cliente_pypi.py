"""
Cliente HTTP para o PyPI Registry com rate limiting e retry.

Endpoints:
  - pypi.org/simple/           — listagem de todos os pacotes (HTML)
  - pypi.org/pypi/{nome}/json  — detalhes JSON de um pacote

Rate limit: 80 req/min (compartilhado com npm).
Retry: backoff exponencial via tenacity.
"""

import time
import threading
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from specter.config import config
from specter.utils.logging_config import obter_logger

log = obter_logger("cliente_pypi")

_URL_BASE = "https://pypi.org"


@dataclass
class _TokenBucket:
    """Rate limiter token bucket (igual ao do npm)."""

    capacidade: int = 80
    tokens: float = field(init=False)
    ultimo_reabastecimento: float = field(init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self):
        self.tokens = float(self.capacidade)
        self.ultimo_reabastecimento = time.monotonic()

    def aguardar(self) -> None:
        with self._lock:
            agora = time.monotonic()
            decorrido = agora - self.ultimo_reabastecimento
            self.tokens = min(
                self.capacidade, self.tokens + decorrido * (self.capacidade / 60.0)
            )
            self.ultimo_reabastecimento = agora

            if self.tokens < 1.0:
                espera = (1.0 - self.tokens) / (self.capacidade / 60.0)
                time.sleep(espera)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


class ClientePyPI:
    """
    Cliente para o PyPI com connection pooling,
    rate limiting e retry automatico.
    """

    def __init__(self):
        self._rate_limiter = _TokenBucket(capacidade=config.NPM_RATE_LIMIT)
        self._client = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
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
    )
    def listar_todos_pacotes(self) -> list[str]:
        """
        Busca lista de todos os pacotes no PyPI via /simple/ (HTML).
        Retorna lista de nomes de pacotes.
        """
        self._rate_limiter.aguardar()

        resp = self._client.get(
            f"{_URL_BASE}/simple/",
            headers={"Accept": "text/html"},
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        nomes = [a.text.strip() for a in soup.find_all("a") if a.text.strip()]

        log.info("pypi_listagem", total_pacotes=len(nomes))
        return nomes

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
    )
    def obter_pacote(self, nome: str) -> dict | None:
        """
        Busca detalhes JSON de um pacote no PyPI.
        Retorna None se 404.
        """
        self._rate_limiter.aguardar()

        try:
            resp = self._client.get(f"{_URL_BASE}/pypi/{nome}/json")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                log.warning("pypi_pacote_nao_encontrado", pacote=nome)
                return None
            raise
