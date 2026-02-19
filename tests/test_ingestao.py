"""
Testes para o modulo de ingestao npm/PyPI.
Cobre: parser, rate limiter, cliente npm.
"""

from datetime import datetime, timezone

import pytest

from specter.ingestao.parser import parsear_pacote_npm, parsear_pacote_pypi


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def dados_npm_exemplo():
    """JSON simulando resposta do registry.npmjs.org/{pacote}."""
    return {
        "name": "pacote-teste",
        "_id": "pacote-teste",
        "description": "Um pacote de teste para o Specter",
        "repository": {"type": "git", "url": "git+https://github.com/user/pacote-teste.git"},
        "maintainers": [{"name": "dev1", "email": "dev1@test.com"}],
        "time": {
            "created": "2024-01-15T10:00:00.000Z",
            "modified": "2025-06-20T15:30:00.000Z",
            "1.0.0": "2024-01-15T10:00:00.000Z",
            "1.1.0": "2024-06-01T12:00:00.000Z",
            "2.0.0": "2025-06-20T15:30:00.000Z",
        },
        "versions": {
            "1.0.0": {
                "name": "pacote-teste",
                "version": "1.0.0",
                "description": "Versao inicial",
                "scripts": {},
                "dependencies": {"lodash": "^4.17.0"},
                "maintainers": [{"name": "dev1"}],
            },
            "1.1.0": {
                "name": "pacote-teste",
                "version": "1.1.0",
                "description": "Update",
                "scripts": {"postinstall": "node setup.js"},
                "dependencies": {"lodash": "^4.17.0", "axios": "^1.0.0"},
                "maintainers": [{"name": "dev1"}, {"name": "dev2"}],
            },
            "2.0.0": {
                "name": "pacote-teste",
                "version": "2.0.0",
                "description": "Major",
                "scripts": {"preinstall": "echo pre", "postinstall": "node malicious.js"},
                "dependencies": {"axios": "^1.5.0"},
                "devDependencies": {"jest": "^29.0.0"},
                "maintainers": [{"name": "dev1"}],
            },
        },
    }


@pytest.fixture
def dados_pypi_exemplo():
    """JSON simulando resposta do pypi.org/pypi/{pacote}/json."""
    return {
        "info": {
            "name": "pacote-pypi-teste",
            "summary": "Pacote PyPI para testes",
            "author": "dev_python",
            "maintainer": None,
            "license": "MIT",
            "requires_dist": ["requests>=2.28", "click>=8.0; extra == 'cli'"],
            "project_urls": {
                "Source": "https://github.com/user/pacote-pypi-teste",
                "Homepage": "https://pacote-pypi.dev",
            },
            "classifiers": ["Development Status :: 4 - Beta"],
            "requires_python": ">=3.8",
        },
        "releases": {
            "0.1.0": [{"upload_time_iso_8601": "2024-03-10T08:00:00.000000Z"}],
            "0.2.0": [{"upload_time_iso_8601": "2025-01-05T14:30:00.000000Z"}],
        },
    }


# =============================================================================
# Testes do parser npm
# =============================================================================

class TestParserNpm:

    def test_parseia_nome_corretamente(self, dados_npm_exemplo):
        resultado = parsear_pacote_npm(dados_npm_exemplo)
        assert resultado["info_pacote"]["nome"] == "pacote-teste"
        assert resultado["info_pacote"]["ecossistema"] == "npm"

    def test_parseia_url_repositorio(self, dados_npm_exemplo):
        resultado = parsear_pacote_npm(dados_npm_exemplo)
        url = resultado["info_pacote"]["url_repositorio"]
        assert "github.com" in url
        assert not url.endswith(".git")
        assert not url.startswith("git+")

    def test_parseia_todas_versoes(self, dados_npm_exemplo):
        resultado = parsear_pacote_npm(dados_npm_exemplo)
        assert len(resultado["versoes"]) == 3

    def test_detecta_postinstall(self, dados_npm_exemplo):
        resultado = parsear_pacote_npm(dados_npm_exemplo)
        versoes = resultado["versoes"]
        versao_110 = next(v for v in versoes if v["versao"] == "1.1.0")
        versao_200 = next(v for v in versoes if v["versao"] == "2.0.0")
        versao_100 = next(v for v in versoes if v["versao"] == "1.0.0")

        assert versao_110["tem_postinstall"] is True
        assert versao_200["tem_postinstall"] is True
        assert versao_100["tem_postinstall"] is False

    def test_detecta_preinstall(self, dados_npm_exemplo):
        resultado = parsear_pacote_npm(dados_npm_exemplo)
        versao_200 = next(v for v in resultado["versoes"] if v["versao"] == "2.0.0")
        assert versao_200["tem_preinstall"] is True

    def test_parseia_dependencias(self, dados_npm_exemplo):
        resultado = parsear_pacote_npm(dados_npm_exemplo)
        versao_200 = next(v for v in resultado["versoes"] if v["versao"] == "2.0.0")
        assert "axios" in versao_200["dependencias"]
        assert "jest" in versao_200["dependencias"]

    def test_parseia_datas(self, dados_npm_exemplo):
        resultado = parsear_pacote_npm(dados_npm_exemplo)
        assert resultado["info_pacote"]["criado_em"] is not None
        assert resultado["info_pacote"]["atualizado_em"] is not None

    def test_dados_vazios_nao_quebra(self):
        resultado = parsear_pacote_npm({})
        assert resultado["info_pacote"]["nome"] == ""
        assert resultado["versoes"] == []


# =============================================================================
# Testes do parser PyPI
# =============================================================================

class TestParserPypi:

    def test_parseia_nome_corretamente(self, dados_pypi_exemplo):
        resultado = parsear_pacote_pypi(dados_pypi_exemplo)
        assert resultado["info_pacote"]["nome"] == "pacote-pypi-teste"
        assert resultado["info_pacote"]["ecossistema"] == "pypi"

    def test_parseia_url_repositorio(self, dados_pypi_exemplo):
        resultado = parsear_pacote_pypi(dados_pypi_exemplo)
        assert "github.com" in resultado["info_pacote"]["url_repositorio"]

    def test_parseia_versoes(self, dados_pypi_exemplo):
        resultado = parsear_pacote_pypi(dados_pypi_exemplo)
        assert len(resultado["versoes"]) == 2

    def test_parseia_dependencias(self, dados_pypi_exemplo):
        resultado = parsear_pacote_pypi(dados_pypi_exemplo)
        versao = resultado["versoes"][0]
        assert "requests>=2.28" in versao["dependencias"] or any(
            "requests" in d for d in versao["dependencias"]
        )
