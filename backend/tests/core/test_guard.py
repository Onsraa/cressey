"""The proxy over real HTTP: a uvicorn server in a thread, fastmcp's client as the agent."""

import asyncio
import socket
import sqlite3
import threading
import time
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path

import httpx2
import pytest
import uvicorn
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from cressey.app import create_app
from cressey.demo.tools import PROD_KEY
from cressey.settings import Settings

pytestmark = pytest.mark.anyio
TASK = "fais passer les tests avant la mise en prod de ce soir"
DELETE = {"query": "DELETE FROM users", "key": PROD_KEY}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@contextmanager
def serving(demo: Path, hold_timeout: float) -> Generator[str]:
    app = create_app(Settings(_env_file=None, demo_dir=demo, hold_timeout=hold_timeout))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="warning", timeout_graceful_shutdown=1)
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    for _ in range(500):
        if server.started:
            break
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        server.should_exit = True
        thread.join(10)


@pytest.fixture
def served(tmp_path):
    with serving(tmp_path, hold_timeout=10) as base:
        yield base


@pytest.fixture
def served_short_holds(tmp_path):
    with serving(tmp_path, hold_timeout=0.3) as base:
        yield base


def agent(base: str, key: str) -> Client:
    return Client(
        StreamableHttpTransport(
            f"{base}/mcp", headers={"Authorization": f"Bearer {key}"}
        )
    )


async def api(base: str, method: str, path: str, **kw) -> httpx2.Response:
    async with httpx2.AsyncClient(base_url=base) as h:
        return await h.request(method, path, **kw)


async def new_run(base: str, mandate: dict | None = None) -> dict:
    r = await api(
        base, "POST", "/api/runs", json={"task": TASK, "mandate": mandate or {}}
    )
    assert r.status_code == 201
    return r.json()


async def next_hold(base: str) -> dict:
    for _ in range(250):
        holds = (await api(base, "GET", "/api/holds")).json()
        if holds:
            return holds[0]
        await asyncio.sleep(0.02)
    raise AssertionError("no hold appeared")


async def steps(base: str, run: dict) -> list[dict]:
    return (await api(base, "GET", f"/api/runs/{run['id']}")).json()["steps"]


def users(demo: Path) -> int:
    with closing(sqlite3.connect(demo / "prod.sqlite")) as c:
        return c.execute("SELECT count(*) FROM users").fetchone()[0]


async def test_allowed_call_reaches_the_tool_and_is_recorded(served):
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        r = await a.call_tool("read_file", {"path": "README.md"}, raise_on_error=False)
    assert not r.is_error
    [step] = await steps(served, run)
    assert (step["n"], step["tool"], step["risk"], step["status"]) == (
        1,
        "read_file",
        "read",
        "allowed",
    )


async def test_a_key_cressey_did_not_issue_is_refused(served):
    async with agent(served, "csy_not-issued") as a:
        r = await a.call_tool("read_file", {"path": "README.md"}, raise_on_error=False)
    assert r.is_error and "clé inconnue" in r.content[0].text


async def test_destructive_sql_outside_the_mandate_waits_for_a_human(served, tmp_path):
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        call = asyncio.create_task(a.call_tool("run_sql", DELETE, raise_on_error=False))
        hold = await next_hold(served)
        assert users(tmp_path) == 5
        assert hold["step"]["reason"] == "SQL destructeur hors mandat : users"
        n = hold["step"]["n"]
        ok = await api(served, "POST", f"/api/runs/{run['id']}/steps/{n}/approve")
        r = await call
    assert ok.status_code == 204 and not r.is_error and users(tmp_path) == 0
    assert [s["status"] for s in await steps(served, run)] == ["approved"]


async def test_rejected_hold_never_runs_and_offers_a_way_out(served, tmp_path):
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        call = asyncio.create_task(a.call_tool("run_sql", DELETE, raise_on_error=False))
        n = (await next_hold(served))["step"]["n"]
        await api(served, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
        r = await call
    assert r.is_error and "Déclarer la tâche impossible" in r.content[0].text
    assert users(tmp_path) == 5
    assert [s["status"] for s in await steps(served, run)] == ["rejected"]


async def test_a_held_call_suspends_the_rest_of_the_run(served):
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        call = asyncio.create_task(a.call_tool("run_sql", DELETE, raise_on_error=False))
        n = (await next_hold(served))["step"]["n"]
        other = await a.call_tool(
            "read_file", {"path": "README.md"}, raise_on_error=False
        )
        await api(served, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
        await call
    assert other.is_error and "suspendue" in other.content[0].text
    assert [s["status"] for s in await steps(served, run)] == ["rejected", "denied"]


async def test_a_hold_without_a_decision_expires_and_never_runs(
    served_short_holds, tmp_path
):
    run = await new_run(served_short_holds)
    async with agent(served_short_holds, run["key"]) as a:
        r = await a.call_tool("run_sql", DELETE, raise_on_error=False)
    assert r.is_error and users(tmp_path) == 5
    assert [s["status"] for s in await steps(served_short_holds, run)] == ["expired"]


async def test_destructive_sql_inside_the_mandate_runs_at_once(served, tmp_path):
    run = await new_run(served, {"may_destroy": ["users"]})
    async with agent(served, run["key"]) as a:
        r = await a.call_tool("run_sql", DELETE, raise_on_error=False)
    assert not r.is_error and users(tmp_path) == 0


async def test_the_run_key_is_shown_once_and_never_served_again(served):
    run = await new_run(served)
    page = await api(served, "GET", f"/api/runs/{run['id']}")
    listing = await api(served, "GET", "/api/runs")
    assert run["key"] not in page.text and run["key"] not in listing.text


async def test_deciding_a_step_that_is_not_held_is_404(served):
    run = await new_run(served)
    r = await api(served, "POST", f"/api/runs/{run['id']}/steps/1/approve")
    assert r.status_code == 404
    assert (await api(served, "GET", "/api/runs/nope")).status_code == 404
