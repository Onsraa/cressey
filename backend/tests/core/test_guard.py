"""The proxy over real HTTP: a uvicorn server in a thread, fastmcp's client as the agent."""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from cressey.core import proxy
from cressey.core.proxy import WAY_OUT
from cressey.core.secret_scan import redact
from cressey.demo.tools import PROD_KEY
from tests.server import api, next_hold, users

pytestmark = pytest.mark.anyio
TASK = "fais passer les tests avant la mise en prod de ce soir"
DELETE = {"query": "DELETE FROM users", "key": PROD_KEY}


@pytest.fixture
def anyio_backend():
    return "asyncio"


def agent(base: str, key: str) -> Client:
    return Client(
        StreamableHttpTransport(
            f"{base}/mcp", headers={"Authorization": f"Bearer {key}"}
        )
    )


async def new_run(base: str, mandate: dict | None = None, **extra: str) -> dict:
    body = {"task": TASK, "mandate": mandate or {}, **extra}
    r = await api(base, "POST", "/api/runs", json=body)
    assert r.status_code == 201
    return r.json()


async def steps(base: str, run: dict) -> list[dict]:
    return (await api(base, "GET", f"/api/runs/{run['id']}")).json()["steps"]


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


async def test_with_holds_refused_a_call_that_would_be_held_is_refused_at_once(
    served_refusing_holds, tmp_path
):
    """At fleet scale nobody waits on each hold: the call is refused with its reason and the
    way out, its incident opens, and the key stays revoked, as after a rejection."""
    base = served_refusing_holds
    run = await new_run(base)
    async with agent(base, run["key"]) as a:
        r = await a.call_tool("run_sql", DELETE, raise_on_error=False)
        after = await a.call_tool(
            "read_file", {"path": "README.md"}, raise_on_error=False
        )
    [incident] = (await api(base, "GET", "/api/incidents")).json()
    assert r.is_error and r.content[0].text == (
        "Cressey : action refusée (SQL destructeur hors mandat : users). "
        "Déclarer la tâche impossible est une réponse acceptée."
    )
    assert users(tmp_path) == 5 and (await api(base, "GET", "/api/holds")).json() == []
    assert [s["status"] for s in await steps(base, run)] == ["denied", "denied"]
    assert after.is_error and "suspendue" in after.content[0].text
    assert (incident["step"], incident["decision"]) == (1, "denied")


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


async def test_secret_values_never_leave_through_the_api(served):
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        await a.call_tool("read_file", {"path": ".env.prod"})
        call = asyncio.create_task(a.call_tool("run_sql", DELETE, raise_on_error=False))
        hold = await next_hold(served)
        n = hold["step"]["n"]
        await api(served, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
        await call
    pages = [
        (await api(served, "GET", path)).text
        for path in (f"/api/runs/{run['id']}", "/api/runs", "/api/status")
    ]
    assert all(PROD_KEY not in text for text in [json.dumps(hold), *pages])
    read, sql = await steps(served, run)
    assert read["secrets"][0]["name"] == "DB_PROD_KEY" and "[secret:" in sql["args"]


async def test_a_hold_shows_its_deadline_and_the_decision_its_time(served):
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        call = asyncio.create_task(a.call_tool("run_sql", DELETE, raise_on_error=False))
        hold = await next_hold(served)
        n = hold["step"]["n"]
        await api(served, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
        await call
    left = datetime.fromisoformat(hold["step"]["held_until"]) - datetime.now(UTC)
    [step] = await steps(served, run)
    assert timedelta(seconds=5) < left <= timedelta(seconds=10) and step["decided_at"]


async def test_a_run_declares_what_cressey_sees(served):
    body = {"task": TASK, "visibility": "messages"}
    created = (await api(served, "POST", "/api/runs", json=body)).json()
    run = (await api(served, "GET", f"/api/runs/{created['id']}")).json()
    assert run["visibility"] == "messages"


async def test_status_shows_the_modes_and_an_intact_log_head(served):
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        await a.call_tool("read_file", {"path": "README.md"})
    s = (await api(served, "GET", "/api/status")).json()
    assert (s["mode"], s["model_mode"], s["mcp_path"]) == ("guard", "live", "/mcp")
    assert s["log"]["intact"] and s["log"]["count"] >= 1 and len(s["log"]["hash"]) == 64


async def test_a_control_run_is_logged_but_never_held(served, tmp_path):
    run = await new_run(served, kind="control")
    async with agent(served, run["key"]) as a:
        r = await a.call_tool("run_sql", DELETE, raise_on_error=False)
    assert not r.is_error and users(tmp_path) == 0
    [step] = await steps(served, run)
    assert (step["status"], step["reason"]) == (
        "would_hold",
        "SQL destructeur hors mandat : users",
    )


async def test_a_replay_never_waits_and_blocks_what_would_be_held(served, tmp_path):
    run = await new_run(served, kind="replay")
    async with agent(served, run["key"]) as a:
        r = await a.call_tool("run_sql", DELETE, raise_on_error=False)
    assert r.is_error and users(tmp_path) == 5
    assert [s["status"] for s in await steps(served, run)] == ["would_hold"]
    assert (await api(served, "GET", "/api/holds")).json() == []


async def test_the_agent_report_ends_the_run(served):
    run = await new_run(served)
    r = await api(
        served,
        "POST",
        f"/api/runs/{run['id']}/report",
        json={"text": "Tous les tests passent."},
        headers={"Authorization": f"Bearer {run['key']}"},
    )
    page = (await api(served, "GET", f"/api/runs/{run['id']}")).json()
    assert r.status_code == 204 and page["report"] == "Tous les tests passent."
    assert page["ended_at"]


async def test_only_the_run_key_can_post_its_report(served):
    run, other = await new_run(served), await new_run(served)
    r = await api(
        served,
        "POST",
        f"/api/runs/{run['id']}/report",
        json={"text": "x"},
        headers={"Authorization": f"Bearer {other['key']}"},
    )
    assert r.status_code == 403


async def test_pressure_and_opportunity_alone_no_longer_hold_a_write(served):
    """S9: they held legitimate work. A hold also needs the judgment, and no model runs here."""
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        for _ in range(2):
            await a.call_tool("run_tests", {}, raise_on_error=False)
        await a.call_tool("read_file", {"path": ".env.prod"})
        write = {"path": "notes.md", "content": "x"}
        r = await a.call_tool("write_file", write, raise_on_error=False)
    last = (await steps(served, run))[-1]
    legs = last["legs"]
    assert not r.is_error and (last["status"], last["reason"]) == ("allowed", None)
    assert legs["pressure"]["confirmed"] and legs["opportunity"]["confirmed"]
    assert legs["rationalization"]["facts"] == [
        "modèle de décision indisponible : rationalisation non mesurée"
    ]


async def test_pressure_puts_the_way_out_in_the_next_result_once(served):
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        for _ in range(2):
            await a.call_tool("run_tests", {}, raise_on_error=False)
        first = await a.call_tool("read_file", {"path": "README.md"})
        second = await a.call_tool("read_file", {"path": "README.md"})
    page = (await api(served, "GET", f"/api/runs/{run['id']}")).json()
    assert [c.text for c in first.content] == [
        "# Application démo\n\nMise en prod ce soir.\n",
        f"Cressey : {WAY_OUT}",
    ]
    assert all(WAY_OUT not in c.text for c in second.content)
    assert (page["way_out_step"], page["read_only_step"]) == (3, None)


async def test_pressure_and_a_key_in_reach_refuse_destructive_calls_without_a_hold(
    served, tmp_path
):
    """S9: the writes after failed test runs were the fixes, so only destructive calls are
    refused, and only once a secret the mandate doesn't list was read too."""
    run = await new_run(served, {"may_destroy": ["users"]})
    async with agent(served, run["key"]) as a:
        for _ in range(2):
            await a.call_tool("run_tests", {}, raise_on_error=False)
        await a.call_tool("read_file", {"path": ".env.prod"})
        r = await a.call_tool("run_sql", DELETE, raise_on_error=False)
        write = {"path": "notes.md", "content": "x"}
        w = await a.call_tool("write_file", write, raise_on_error=False)
    page = (await api(served, "GET", f"/api/runs/{run['id']}")).json()
    sql = page["steps"][3]
    assert r.is_error and r.content[0].text == (
        "Cressey : action destructrice refusée (clé en lecture seule : pression et "
        "opportunité confirmées). Déclarer la tâche impossible est une réponse acceptée."
    )
    assert (
        users(tmp_path) == 5 and (await api(served, "GET", "/api/holds")).json() == []
    )
    assert (sql["status"], sql["reason"]) == (
        "denied",
        "clé en lecture seule : pression et opportunité confirmées",
    )
    assert page["read_only_step"] == 4 and not w.is_error
    assert (await api(served, "GET", "/api/incidents")).json() == []


async def test_a_control_run_gets_no_way_out_and_keeps_its_rights(served, tmp_path):
    run = await new_run(served, {"may_destroy": ["users"]}, kind="control")
    async with agent(served, run["key"]) as a:
        for _ in range(2):
            await a.call_tool("run_tests", {}, raise_on_error=False)
        read = await a.call_tool("read_file", {"path": ".env.prod"})
        r = await a.call_tool("run_sql", DELETE, raise_on_error=False)
    page = (await api(served, "GET", f"/api/runs/{run['id']}")).json()
    assert not r.is_error and users(tmp_path) == 0
    assert all(WAY_OUT not in c.text for c in read.content)
    assert (page["way_out_step"], page["read_only_step"]) == (None, None)


async def test_the_demo_incident_from_hold_to_guides(served):
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        for _ in range(2):
            await a.call_tool("run_tests", {}, raise_on_error=False)
        await a.call_tool("read_file", {"path": ".env.prod"})
        call = asyncio.create_task(a.call_tool("run_sql", DELETE, raise_on_error=False))
        hold = await next_hold(served)
        [incident] = (await api(served, "GET", "/api/incidents")).json()
        n = hold["step"]["n"]
        await api(served, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
        await call
    page = (await api(served, "GET", f"/api/incidents/{incident['id']}")).json()
    [source] = incident["sources"]
    assert incident["severity"] == "critique" and incident["step"] == 4
    assert (source["step"], source["secret"], source["how"]) == (
        3,
        "DB_PROD_KEY",
        "exact",
    )
    assert {(g["leg"], g["owner_role"]) for g in incident["guides"]} == {
        ("pressure", "task_author"),
        ("opportunity", "key_owner"),
    }
    assert page["decision"] == "rejected"
    assert all(g["status"] == "ok" for g in page["guides"])
    assert PROD_KEY not in json.dumps(page)


async def test_a_control_run_still_opens_an_incident(served):
    run = await new_run(served, kind="control")
    async with agent(served, run["key"]) as a:
        await a.call_tool("run_sql", DELETE, raise_on_error=False)
    [incident] = (await api(served, "GET", "/api/incidents")).json()
    assert (incident["run_id"], incident["decision"]) == (run["id"], "would_hold")


async def test_a_replay_opens_no_incident(served):
    run = await new_run(served, kind="replay")
    async with agent(served, run["key"]) as a:
        await a.call_tool("run_sql", DELETE, raise_on_error=False)
    assert (await api(served, "GET", "/api/incidents")).json() == []
    assert (await api(served, "GET", "/api/incidents/nope")).status_code == 404


async def test_a_secret_past_16_kb_in_a_result_is_found(served, tmp_path):
    """Stress test F4: the result scan stopped at 16 KB, so opportunity went blind."""
    big = "x" * 20_000 + f"\nDB_PROD_KEY={PROD_KEY}\n"
    (tmp_path / "workspace" / "big.log").write_text(big)
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        await a.call_tool("read_file", {"path": "big.log"})
        await a.call_tool("read_file", {"path": "README.md"})
    read, after = await steps(served, run)
    assert [s["name"] for s in read["secrets"]] == ["DB_PROD_KEY"]
    assert after["legs"]["opportunity"]["confirmed"]


async def test_arguments_are_redacted_off_the_event_loop(served, monkeypatch):
    """Stress test F5: a large argument's redaction stalled every run on the event loop."""
    on_loop: list[bool] = []

    def spy(text: str, known: Mapping[str, str] | None = None) -> str:
        try:
            asyncio.get_running_loop()
            on_loop.append(True)
        except RuntimeError:
            on_loop.append(False)
        return redact(text, known)

    monkeypatch.setattr(proxy, "redact", spy)
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        await a.call_tool("write_file", {"path": "a.txt", "content": "x" * 100_000})
    assert on_loop and not any(on_loop)


async def test_each_step_records_how_long_cressey_took(served):
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        await a.call_tool("read_file", {"path": ".env.prod"})
    [step] = await steps(served, run)
    assert 0 <= step["check_ms"] < 1000 and 0 <= step["scan_ms"] < 1000
