"""The dashboard polls every second: it gets each run's summary, and a run's steps on demand."""

import pytest

from cressey.testing import agent, api

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_the_runs_poll_serves_summaries_and_a_run_its_steps(served):
    body = {"task": "Fix the failing test"}
    run = (await api(served, "POST", "/api/runs", json=body)).json()
    async with agent(served, run["key"]) as a:
        await a.call_tool("read_file", {"path": "README.md"})
    [summary] = (await api(served, "GET", "/api/runs")).json()
    page = (await api(served, "GET", f"/api/runs/{run['id']}")).json()
    assert summary == {
        "id": run["id"],
        "task": "Fix the failing test",
        "kind": "live",
        "via": "mcp",
        "started_at": page["started_at"],
        "calls": 1,
    }
    assert [s["tool"] for s in page["steps"]] == ["read_file"]
