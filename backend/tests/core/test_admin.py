"""The control plane needs the admin key; the agent's run key never opens it."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cressey.app import create_app
from cressey.settings import Settings
from tests.server import ADMIN, ADMIN_AUTH

CONTROL = [
    ("GET", "/api/runs"),
    ("GET", "/api/holds"),
    ("GET", "/api/incidents"),
    ("GET", "/api/status"),
    ("GET", "/api/policy/responses"),
    ("POST", "/api/runs/r1/unlock"),
    ("POST", "/api/runs/r1/steps/1/approve"),
    ("POST", "/api/runs/r1/steps/1/reject"),
    ("GET", "/api/guides/g1"),
]


def _app(admin: str | None = ADMIN) -> FastAPI:
    s = Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        admin_token=admin,
    )
    return create_app(s)


def _client(admin: str | None = ADMIN) -> TestClient:
    return TestClient(_app(admin))


@pytest.mark.parametrize(("method", "path"), CONTROL)
def test_the_control_plane_refuses_a_call_without_the_admin_key(method, path):
    assert _client().request(method, path).status_code == 401


def test_the_agents_run_key_never_opens_the_control_plane():
    c = _client()
    run = c.post(
        "/api/runs", json={"task": "Fix the failing test"}, headers=ADMIN_AUTH
    ).json()
    as_agent = {"Authorization": f"Bearer {run['key']}"}
    policy = c.get("/api/policy/responses", headers=ADMIN_AUTH).json()
    every_check_on_alert = {k: "alert" for k in policy}
    put = c.put("/api/policy/responses", json=every_check_on_alert, headers=as_agent)
    assert put.status_code == 401
    assert c.post(f"/api/runs/{run['id']}/unlock", headers=as_agent).status_code == 401
    assert c.get("/api/policy/responses", headers=ADMIN_AUTH).json() == policy


def test_the_admin_key_opens_it_and_the_agent_keeps_its_own_routes():
    c = _client()
    run = c.post(
        "/api/runs", json={"task": "Fix the failing test"}, headers=ADMIN_AUTH
    ).json()
    assert c.get("/api/runs", headers=ADMIN_AUTH).status_code == 200
    as_agent = {"Authorization": f"Bearer {run['key']}"}
    said = c.post(
        f"/api/runs/{run['id']}/messages", json={"text": "hi"}, headers=as_agent
    )
    assert said.status_code == 204
    assert c.get("/api/health").status_code == 200


def test_unset_the_key_is_random_so_the_control_plane_stays_locked():
    app = _app(admin=None)
    assert app.state.admin_token
    c = TestClient(app)
    guessed = {"Authorization": "Bearer "}
    assert c.get("/api/runs", headers=guessed).status_code == 401
    assert c.get("/api/runs").status_code == 401
