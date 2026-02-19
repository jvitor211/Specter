"""
Extrator de features de seguranca para pacotes npm/PyPI.

Recebe um registro de pacote (dict ou dados do banco) e retorna um dicionario
com todas as features usadas pelo modelo Wings para classificacao de risco.

Features computadas:
  - Temporais: idade, frequencia de publicacao, pacote novo
  - Sociais: mantenedores, GitHub (estrelas, idade, contribuidores)
  - Risco comportamental: scripts postinstall/preinstall
  - Typosquatting: similaridade Levenshtein com top-500
"""

from datetime import datetime, timezone
from typing import Any

from rapidfuzz import fuzz as rapidfuzz_fuzz
from rapidfuzz.distance import Levenshtein

from specter.features.top_pacotes import obter_top_500
from specter.features.cliente_github import ClienteGitHub
from specter.utils.logging_config import obter_logger

log = obter_logger("extrator_features")

_LIMIAR_TYPOSQUAT = 0.85
_DIAS_PACOTE_NOVO = 30


def _dias_desde(data: Any) -> int | None:
    """Calcula dias entre uma data e agora. Retorna None se invalido."""
    if data is None:
        return None
    if isinstance(data, str):
        try:
            data = datetime.fromisoformat(data.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(data, datetime):
        if data.tzinfo is None:
            data = data.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - data).days
    return None


def _calcular_typosquatting(nome: str, top_500: list[str]) -> dict:
    """
    Calcula metricas de typosquatting contra a lista de pacotes populares.

    Retorna:
      - score_typosquatting: maior similaridade normalizada (0-100)
      - distancia_edicao_minima: menor edit distance absoluta
      - provavel_typosquat: True se score > 85 e nao esta na lista
    """
    if not top_500 or not nome:
        return {
            "score_typosquatting": 0.0,
            "distancia_edicao_minima": 999,
            "provavel_typosquat": False,
        }

    nome_lower = nome.lower().strip()

    if nome_lower in {p.lower() for p in top_500}:
        return {
            "score_typosquatting": 100.0,
            "distancia_edicao_minima": 0,
            "provavel_typosquat": False,
        }

    melhor_score = 0.0
    menor_distancia = 999

    for pacote_popular in top_500:
        pop_lower = pacote_popular.lower()

        score = rapidfuzz_fuzz.ratio(nome_lower, pop_lower)
        if score > melhor_score:
            melhor_score = score

        dist = Levenshtein.distance(nome_lower, pop_lower)
        if dist < menor_distancia:
            menor_distancia = dist

    return {
        "score_typosquatting": round(melhor_score, 2),
        "distancia_edicao_minima": menor_distancia,
        "provavel_typosquat": melhor_score > (_LIMIAR_TYPOSQUAT * 100),
    }


def extrair_features(registro: dict, cliente_github: ClienteGitHub | None = None) -> dict:
    """
    Extrai todas as features de seguranca de um registro de pacote.

    Parametros:
      registro: dict com campos:
        - nome: str
        - versoes: list[dict] (cada uma com publicado_em, mantenedores, scripts, dependencias)
        - data_criacao: str/datetime
        - url_repositorio: str | None
        - descricao: str | None

      cliente_github: instancia opcional de ClienteGitHub (para reutilizar conexao)

    Retorna:
      dict com todas as features computadas.
    """
    nome = registro.get("nome", "")
    versoes = registro.get("versoes", [])
    data_criacao = registro.get("data_criacao")
    url_repo = registro.get("url_repositorio", "")
    descricao = registro.get("descricao", "")

    # --- Features Temporais ---
    idade_dias = _dias_desde(data_criacao)

    datas_publicacao = []
    for v in versoes:
        d = v.get("publicado_em")
        if d:
            dias = _dias_desde(d)
            if dias is not None:
                datas_publicacao.append(dias)

    dias_desde_ultima = min(datas_publicacao) if datas_publicacao else None
    total_versoes = len(versoes)

    frequencia_versoes = None
    if idade_dias and idade_dias > 0 and total_versoes > 0:
        frequencia_versoes = round(total_versoes / idade_dias, 6)

    pacote_novo = bool(idade_dias is not None and idade_dias < _DIAS_PACOTE_NOVO)

    # --- Features Sociais ---
    todos_mantenedores = set()
    for v in versoes:
        for m in v.get("mantenedores", []):
            if isinstance(m, dict):
                todos_mantenedores.add(m.get("name", m.get("email", "")))
            elif isinstance(m, str):
                todos_mantenedores.add(m)

    contagem_mantenedores = len(todos_mantenedores) if todos_mantenedores else None
    if not contagem_mantenedores and versoes:
        contagem_mantenedores = max(
            (v.get("contagem_mantenedores", 0) for v in versoes), default=0
        )

    mantenedor_unico = contagem_mantenedores == 1 if contagem_mantenedores else False

    # GitHub
    tem_github = bool(url_repo and "github.com" in str(url_repo).lower())
    estrelas_github = None
    idade_github_dias = None
    contribuidores_github = None

    if tem_github and url_repo:
        _gh = cliente_github or ClienteGitHub()
        try:
            info_repo = _gh.obter_info_repo(url_repo)
            if info_repo:
                estrelas_github = info_repo.estrelas
                idade_github_dias = info_repo.idade_dias
                contribuidores_github = info_repo.contribuidores
        except Exception as e:
            log.warning("github_feature_erro", pacote=nome, erro=str(e))
        finally:
            if not cliente_github:
                _gh.fechar()

    # --- Features de Risco Comportamental ---
    tem_postinstall = False
    tem_preinstall = False
    tamanho_script_max = 0

    for v in versoes:
        scripts = v.get("scripts", {}) or {}
        if "postinstall" in scripts:
            tem_postinstall = True
            tamanho_script_max = max(
                tamanho_script_max, len(str(scripts.get("postinstall", "")))
            )
        if "preinstall" in scripts:
            tem_preinstall = True
            tamanho_script_max = max(
                tamanho_script_max, len(str(scripts.get("preinstall", "")))
            )

    # --- Features de Typosquatting ---
    top_500 = obter_top_500()
    typo_features = _calcular_typosquatting(nome, top_500)

    if typo_features["provavel_typosquat"] and idade_dias is not None and idade_dias >= 90:
        typo_features["provavel_typosquat"] = False

    # --- Features de Dependencias ---
    todas_deps = set()
    for v in versoes:
        deps = v.get("dependencias", {}) or {}
        todas_deps.update(deps.keys())
    num_dependencias = len(todas_deps)

    # --- Tamanho da Descricao ---
    tamanho_descricao = len(descricao) if descricao else 0

    features = {
        # Temporais
        "idade_pacote_dias": idade_dias,
        "dias_desde_ultima_publicacao": dias_desde_ultima,
        "total_versoes": total_versoes,
        "frequencia_versoes": frequencia_versoes,
        "pacote_novo": int(pacote_novo),

        # Sociais
        "contagem_mantenedores": contagem_mantenedores,
        "mantenedor_unico": int(mantenedor_unico),
        "tem_github": int(tem_github),
        "estrelas_github": estrelas_github,
        "idade_github_dias": idade_github_dias,
        "contribuidores_github": contribuidores_github,

        # Risco comportamental
        "tem_script_postinstall": int(tem_postinstall),
        "tem_script_preinstall": int(tem_preinstall),
        "tamanho_script_instalacao": tamanho_script_max,

        # Typosquatting
        "score_typosquatting": typo_features["score_typosquatting"],
        "distancia_edicao_minima": typo_features["distancia_edicao_minima"],
        "provavel_typosquat": int(typo_features["provavel_typosquat"]),

        # Extras
        "num_dependencias": num_dependencias,
        "tamanho_descricao": tamanho_descricao,
    }

    log.debug(
        "features_extraidas",
        pacote=nome,
        score_typo=features["score_typosquatting"],
        tem_postinstall=tem_postinstall,
    )

    return features
