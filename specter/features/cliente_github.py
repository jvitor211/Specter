"""
Cliente para a GitHub API com cache Redis e graceful degradation.

Extrai: estrelas, data de criacao, numero de contribuidores de um repositorio.
Rate limit: 5000 req/h com token, 60 req/h sem.
Cache: Redis com TTL de 1 hora para evitar consultas repetidas.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import redis

from specter.config import config
from specter.utils.logging_config import obter_logger

log = obter_logger("cliente_github")

_URL_BASE = "https://api.github.com"
_CACHE_TTL = 3600  # 1 hora
_REGEX_GITHUB = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/\s#?]+)", re.IGNORECASE
)


@dataclass
class InfoRepositorio:
    """Dados extraidos de um repositorio GitHub."""

    proprietario: str
    nome: str
    estrelas: int
    data_criacao: datetime | None
    idade_dias: int | None
    contribuidores: int | None
    fork: bool
    arquivado: bool


def _extrair_owner_repo(url: str) -> tuple[str, str] | None:
    """Extrai owner/repo de uma URL GitHub."""
    match = _REGEX_GITHUB.search(url)
    if not match:
        return None
    owner = match.group(1)
    repo = match.group(2).rstrip(".git")
    return owner, repo


def _obter_redis() -> redis.Redis | None:
    """Retorna conexao Redis ou None se indisponivel."""
    try:
        r = redis.from_url(config.REDIS_URL, decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None


class ClienteGitHub:
    """
    Cliente para GitHub API com:
    - Token via GITHUB_TOKEN (5000 req/h)
    - Cache Redis (TTL 1h)
    - Graceful degradation (retorna None se API falhar)
    """

    def __init__(self, token: str | None = None):
        self._token = token or config.GITHUB_TOKEN
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client = httpx.Client(
            base_url=_URL_BASE,
            headers=headers,
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
        )
        self._redis = _obter_redis()

    def fechar(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.fechar()

    def _chave_cache(self, owner: str, repo: str) -> str:
        return f"specter:github:{owner}/{repo}"

    def _buscar_cache(self, owner: str, repo: str) -> InfoRepositorio | None:
        if not self._redis:
            return None
        try:
            dados = self._redis.get(self._chave_cache(owner, repo))
            if dados:
                d = json.loads(dados)
                return InfoRepositorio(
                    proprietario=d["proprietario"],
                    nome=d["nome"],
                    estrelas=d["estrelas"],
                    data_criacao=datetime.fromisoformat(d["data_criacao"]) if d.get("data_criacao") else None,
                    idade_dias=d.get("idade_dias"),
                    contribuidores=d.get("contribuidores"),
                    fork=d.get("fork", False),
                    arquivado=d.get("arquivado", False),
                )
        except Exception:
            pass
        return None

    def _salvar_cache(self, owner: str, repo: str, info: InfoRepositorio) -> None:
        if not self._redis:
            return
        try:
            dados = {
                "proprietario": info.proprietario,
                "nome": info.nome,
                "estrelas": info.estrelas,
                "data_criacao": info.data_criacao.isoformat() if info.data_criacao else None,
                "idade_dias": info.idade_dias,
                "contribuidores": info.contribuidores,
                "fork": info.fork,
                "arquivado": info.arquivado,
            }
            self._redis.setex(
                self._chave_cache(owner, repo),
                _CACHE_TTL,
                json.dumps(dados),
            )
        except Exception as e:
            log.warning("github_cache_erro", erro=str(e))

    def obter_info_repo(self, url_github: str) -> InfoRepositorio | None:
        """
        Busca informacoes de um repositorio a partir da URL.
        Retorna None se URL invalida, 404, ou API indisponivel.
        """
        parsed = _extrair_owner_repo(url_github)
        if not parsed:
            return None

        owner, repo = parsed

        cached = self._buscar_cache(owner, repo)
        if cached:
            log.debug("github_cache_hit", repo=f"{owner}/{repo}")
            return cached

        try:
            resp = self._client.get(f"/repos/{owner}/{repo}")
            if resp.status_code == 404:
                log.debug("github_repo_nao_encontrado", repo=f"{owner}/{repo}")
                return None
            resp.raise_for_status()
            dados = resp.json()

            data_criacao = None
            idade_dias = None
            if dados.get("created_at"):
                data_criacao = datetime.fromisoformat(
                    dados["created_at"].replace("Z", "+00:00")
                )
                idade_dias = (datetime.now(timezone.utc) - data_criacao).days

            contribuidores = None
            try:
                resp_contrib = self._client.get(
                    f"/repos/{owner}/{repo}/contributors",
                    params={"per_page": 1, "anon": "true"},
                )
                if resp_contrib.status_code == 200:
                    link = resp_contrib.headers.get("Link", "")
                    if 'rel="last"' in link:
                        import re as _re
                        match = _re.search(r"page=(\d+)>; rel=\"last\"", link)
                        if match:
                            contribuidores = int(match.group(1))
                    else:
                        contribuidores = len(resp_contrib.json())
            except Exception:
                pass

            info = InfoRepositorio(
                proprietario=owner,
                nome=repo,
                estrelas=dados.get("stargazers_count", 0),
                data_criacao=data_criacao,
                idade_dias=idade_dias,
                contribuidores=contribuidores,
                fork=dados.get("fork", False),
                arquivado=dados.get("archived", False),
            )

            self._salvar_cache(owner, repo, info)
            log.info(
                "github_info_obtida",
                repo=f"{owner}/{repo}",
                estrelas=info.estrelas,
            )
            return info

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                log.warning("github_rate_limit_excedido")
            else:
                log.warning("github_erro_http", status=e.response.status_code)
            return None
        except Exception as e:
            log.warning("github_erro_geral", erro=str(e))
            return None
