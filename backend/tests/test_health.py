from fastapi.testclient import TestClient

from cressey.app import create_app
from cressey.settings import Settings


def test_health_without_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    r = TestClient(create_app(Settings(_env_file=None))).get("/api/health")
    assert r.status_code == 200 and r.json() == {
        "status": "ok",
        "models": "missing-keys",
    }


def test_health_with_keys():
    s = Settings(_env_file=None, openai_api_key="x", typesafe_api_key="y")
    assert TestClient(create_app(s)).get("/api/health").json()["models"] == "configured"


def test_unknown_api_route_is_404():
    assert (
        TestClient(create_app(Settings(_env_file=None))).get("/api/nope").status_code
        == 404
    )
