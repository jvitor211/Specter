"""
Testes para a API FastAPI do Specter.
Testa endpoints de health e validacao de schemas.
"""

import pytest
from fastapi.testclient import TestClient

from specter.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealth:

    def test_health_retorna_200(self, client):
        resp = client.get("/v1/health")
        assert resp.status_code == 200
        dados = resp.json()
        assert dados["status"] == "ok"
        assert "versao_api" in dados
        assert "modelo_carregado" in dados
        assert "timestamp" in dados

    def test_health_versao_api(self, client):
        resp = client.get("/v1/health")
        assert resp.json()["versao_api"] == "0.1.0"


class TestScanValidacao:

    def test_scan_sem_api_key_retorna_401(self, client):
        resp = client.post("/v1/scan", json={"packages": [{"name": "lodash"}]})
        assert resp.status_code == 401

    def test_scan_com_key_invalida_retorna_401(self, client):
        resp = client.post(
            "/v1/scan",
            json={"packages": [{"name": "lodash"}]},
            headers={"X-Specter-Key": "spk_live_invalida"},
        )
        assert resp.status_code == 401


class TestKeysValidacao:

    def test_criar_chave_sem_email_retorna_422(self, client):
        resp = client.post("/v1/keys/create", json={})
        assert resp.status_code == 422

    def test_uso_sem_auth_retorna_401(self, client):
        resp = client.get("/v1/keys/usage")
        assert resp.status_code == 401


class TestFeedbackValidacao:

    def test_feedback_sem_auth_retorna_401(self, client):
        resp = client.post(
            "/v1/feedback",
            json={"package": "test", "is_false_positive": True},
        )
        assert resp.status_code == 401


class TestPacoteValidacao:

    def test_pacote_sem_auth_retorna_401(self, client):
        resp = client.get("/v1/package/npm/lodash")
        assert resp.status_code == 401
