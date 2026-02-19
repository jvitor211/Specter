"""
Parser de dados do npm/PyPI registry para modelos SQLAlchemy.
Transforma JSON bruto em objetos Pacote/VersaoPacote prontos para upsert.
"""

from datetime import datetime, timezone
from typing import Any

from specter.utils.logging_config import obter_logger

log = obter_logger("parser")


def _parsear_data(valor: Any) -> datetime | None:
    """Converte string ISO para datetime. Retorna None se invalido."""
    if not valor:
        return None
    try:
        if isinstance(valor, str):
            valor = valor.replace("Z", "+00:00")
            return datetime.fromisoformat(valor)
        return None
    except (ValueError, TypeError):
        return None


def parsear_pacote_npm(dados: dict) -> dict:
    """
    Transforma o JSON de registry.npmjs.org/{nome} em dict normalizado.

    Retorna dict com:
      - info_pacote: dados do pacote principal
      - versoes: lista de dicts com dados de cada versao
    """
    nome = dados.get("name", dados.get("_id", ""))
    tempo = dados.get("time", {})

    data_criacao = _parsear_data(tempo.get("created"))
    data_modificacao = _parsear_data(tempo.get("modified"))

    repo = dados.get("repository", {})
    url_repo = None
    if isinstance(repo, dict):
        url_repo = repo.get("url", "")
    elif isinstance(repo, str):
        url_repo = repo
    if url_repo:
        url_repo = url_repo.replace("git+", "").replace("git://", "https://").rstrip(".git")

    descricao = dados.get("description", "")
    if isinstance(descricao, dict):
        descricao = str(descricao)

    info_pacote = {
        "nome": nome,
        "ecossistema": "npm",
        "descricao": (descricao or "")[:2000],
        "url_repositorio": (url_repo or "")[:512] if url_repo else None,
        "criado_em": data_criacao,
        "atualizado_em": data_modificacao or datetime.now(timezone.utc),
    }

    versoes_dict = dados.get("versions", {})
    mantenedores_raiz = dados.get("maintainers", [])
    versoes = []

    for num_versao, info_versao in versoes_dict.items():
        if not isinstance(info_versao, dict):
            continue

        scripts = info_versao.get("scripts", {}) or {}
        deps = info_versao.get("dependencies", {}) or {}
        dev_deps = info_versao.get("devDependencies", {}) or {}
        manutentores = info_versao.get("maintainers", mantenedores_raiz) or []

        tem_postinstall = "postinstall" in scripts
        tem_preinstall = "preinstall" in scripts

        data_pub = _parsear_data(tempo.get(num_versao))

        versoes.append({
            "versao": num_versao,
            "publicado_em": data_pub,
            "contagem_mantenedores": len(manutentores),
            "tem_postinstall": tem_postinstall,
            "tem_preinstall": tem_preinstall,
            "descricao": (info_versao.get("description", "") or "")[:2000],
            "scripts": scripts,
            "dependencias": {**deps, **dev_deps},
            "mantenedores": manutentores,
            "metadados": {
                "license": info_versao.get("license"),
                "homepage": info_versao.get("homepage"),
                "keywords": info_versao.get("keywords", []),
            },
        })

    log.debug("pacote_parseado", pacote=nome, total_versoes=len(versoes))

    return {"info_pacote": info_pacote, "versoes": versoes}


def parsear_pacote_pypi(dados: dict) -> dict:
    """
    Transforma o JSON de pypi.org/pypi/{nome}/json em dict normalizado.
    """
    info = dados.get("info", {})
    releases = dados.get("releases", {})

    nome = info.get("name", "")

    urls_projeto = info.get("project_urls") or {}
    url_repo = (
        urls_projeto.get("Source")
        or urls_projeto.get("Repository")
        or urls_projeto.get("Homepage")
        or ""
    )

    datas_release: list[datetime] = []
    for arquivos in releases.values():
        for arq in (arquivos if isinstance(arquivos, list) else []):
            dt = _parsear_data(arq.get("upload_time_iso_8601"))
            if dt:
                datas_release.append(dt)

    datas_release.sort()
    data_criacao = datas_release[0] if datas_release else None
    data_modificacao = datas_release[-1] if datas_release else None

    info_pacote = {
        "nome": nome,
        "ecossistema": "pypi",
        "descricao": (info.get("summary", "") or "")[:2000],
        "url_repositorio": url_repo[:512] if url_repo else None,
        "criado_em": data_criacao,
        "atualizado_em": data_modificacao or datetime.now(timezone.utc),
    }

    deps_requeridos = info.get("requires_dist") or []
    entry_points = info.get("project_urls", {})

    versoes = []
    for num_versao, arquivos in releases.items():
        if not arquivos:
            continue

        data_pub = None
        for arq in (arquivos if isinstance(arquivos, list) else []):
            dt = _parsear_data(arq.get("upload_time_iso_8601"))
            if dt:
                data_pub = dt
                break

        autor = info.get("author") or info.get("maintainer") or ""
        mantenedor = info.get("maintainer") or ""

        manutentores = []
        if autor:
            manutentores.append({"name": autor})
        if mantenedor and mantenedor != autor:
            manutentores.append({"name": mantenedor})

        versoes.append({
            "versao": num_versao,
            "publicado_em": data_pub,
            "contagem_mantenedores": len(manutentores),
            "tem_postinstall": False,
            "tem_preinstall": False,
            "descricao": (info.get("summary", "") or "")[:2000],
            "scripts": {},
            "dependencias": {d.split(";")[0].strip(): "" for d in deps_requeridos},
            "mantenedores": manutentores,
            "metadados": {
                "license": info.get("license"),
                "classifiers": info.get("classifiers", []),
                "requires_python": info.get("requires_python"),
                "entry_points": entry_points,
            },
        })

    log.debug("pacote_pypi_parseado", pacote=nome, total_versoes=len(versoes))

    return {"info_pacote": info_pacote, "versoes": versoes}
