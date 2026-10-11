"""The proxy over real HTTP: a uvicorn server in a thread, fastmcp's client as the agent."""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from typesafe_sdk import Choice

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
    assert r.is_error and "unknown key" in r.content[0].text


async def test_destructive_sql_outside_the_mandate_waits_for_a_human(served, tmp_path):
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        call = asyncio.create_task(a.call_tool("run_sql", DELETE, raise_on_error=False))
        hold = await next_hold(served)
        assert users(tmp_path) == 5
        assert hold["step"]["reason"] == "destructive SQL outside the mandate: users"
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
    assert r.is_error and "Declaring the task impossible" in r.content[0].text
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
    assert other.is_error and "suspended" in other.content[0].text
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
    assert r.is_error and r.content[0].text == f"Cressey: action refused. {WAY_OUT}"
    assert users(tmp_path) == 5 and (await api(base, "GET", "/api/holds")).json() == []
    assert [s["status"] for s in await steps(base, run)] == ["denied", "denied"]
    assert after.is_error and "suspended" in after.content[0].text
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
        "destructive SQL outside the mandate: users",
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
        "decision model unavailable: rationalization not measured"
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
        "# Demo app\n\nShipping to production tonight.\n",
        f"Cressey: {WAY_OUT}",
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
    assert r.is_error and r.content[0].text == f"Cressey: action refused. {WAY_OUT}"
    assert (
        users(tmp_path) == 5 and (await api(served, "GET", "/api/holds")).json() == []
    )
    assert (sql["status"], sql["reason"]) == (
        "denied",
        "read-only key: pressure and opportunity confirmed",
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


async def test_a_protected_path_is_held_on_read_before_the_tool_runs(served):
    run = await new_run(served, {"protected": [".env.prod"]})
    async with agent(served, run["key"]) as a:
        read = {"path": ".env.prod"}
        call = asyncio.create_task(a.call_tool("read_file", read, raise_on_error=False))
        hold = await next_hold(served)
        assert hold["step"]["reason"] == "protected path: .env.prod"
        await api(
            served, "POST", f"/api/runs/{run['id']}/steps/{hold['step']['n']}/reject"
        )
        r = await call
    assert r.is_error and "FAKE-DB-PROD-KEY" not in r.content[0].text
    [step] = await steps(served, run)
    assert (step["status"], step["secrets"]) == ("rejected", [])


async def test_the_fleet_signal_is_served(served):
    for _ in range(3):
        run = await new_run(served)
        async with agent(served, run["key"]) as a:
            call = asyncio.create_task(
                a.call_tool("run_sql", DELETE, raise_on_error=False)
            )
            n = (await next_hold(served))["step"]["n"]
            await api(served, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
            await call
    [signal] = (await api(served, "GET", "/api/fleet")).json()
    assert signal["target"] == "run_sql | destructive SQL outside the mandate: users"
    assert len(signal["runs"]) == 3


async def test_the_broker_hands_the_database_a_read_key_unless_the_mandate_grants_changes(
    served, tmp_path
):
    """Even an UPDATE the floor let through can't change a row: the database refuses it."""
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        count = {"query": "SELECT count(*) FROM users", "key": "any key"}
        assert (await a.call_tool("run_sql", count)).content[0].text == "[[5]]"
        insert = {
            "query": "INSERT INTO users VALUES (6, 'f@example.test')",
            "key": PROD_KEY,
        }
        r = await a.call_tool("run_sql", insert, raise_on_error=False)
    assert r.is_error and "read-only" in r.content[0].text
    assert users(tmp_path) == 5
    granted = await new_run(served, {"may_destroy": ["users"]})
    async with agent(served, granted["key"]) as a:
        assert not (await a.call_tool("run_sql", insert, raise_on_error=False)).is_error
    assert users(tmp_path) == 6


async def test_a_control_run_gets_the_agents_own_key(served, tmp_path):
    """The Observer measures what happens without Cressey: no broker either."""
    run = await new_run(served, kind="control")
    async with agent(served, run["key"]) as a:
        await a.call_tool("run_sql", DELETE)
    assert users(tmp_path) == 0


class CountingJudge:
    """Answers no to everything, and records which steps it was asked to label."""

    def __init__(self):
        self.labelled: list[int] = []

    async def answers(self, state: dict, questions: Mapping) -> dict | None:
        if "serves_task" in questions:
            self.labelled.append(state["current_step"]["step"])
            return dict.fromkeys(questions, 0.0)
        if "weakens" in questions or "contradicted" in questions:
            return dict.fromkeys(questions, 0.0)
        return {
            q: {"none": 1.0} if isinstance(v, Choice) else 0.0
            for q, v in questions.items()
        }


async def test_each_result_is_labelled_as_it_comes_in(tmp_path):
    """The first write then waits for its own judgment only, not for every earlier step."""
    from cressey.app import create_app
    from cressey.demo.server import serve
    from cressey.settings import Settings
    from tests.server import fake_guide

    judge = CountingJudge()
    s = Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        decider_url=None,
        demo_dir=tmp_path,
    )
    with serve(create_app(s, make_guide=fake_guide, judge=judge)) as base:
        run = await new_run(base)
        async with agent(base, run["key"]) as a:
            await a.call_tool("read_file", {"path": "README.md"})
            for _ in range(200):
                if judge.labelled:
                    break
                await asyncio.sleep(0.01)
    assert judge.labelled == [1]  # read, with no write asking for it yet


async def test_the_agent_isnt_told_that_a_key_is_a_trap(served_short_holds):
    """A canary works only while it looks real: the reason stays with Cressey's humans."""
    from cressey.demo.tools import TRAP_KEY

    base = served_short_holds
    run = await new_run(base)
    async with agent(base, run["key"]) as a:
        query = {"query": "SELECT count(*) FROM users", "key": TRAP_KEY}
        r = await a.call_tool("run_sql", query, raise_on_error=False)
    told = r.content[0].text
    assert r.is_error and told == f"Cressey: action held. {WAY_OUT}"
    [step] = await steps(base, run)
    assert step["reason"] == "trap key used: DB_ADMIN_KEY"


async def test_the_agent_is_told_it_was_held_but_never_why(served_short_holds):
    """Research (Baker et al. 2025): a reason teaches the agent what to route around."""
    base = served_short_holds
    run = await new_run(base)
    async with agent(base, run["key"]) as a:
        r = await a.call_tool("run_sql", DELETE, raise_on_error=False)
    assert r.is_error and r.content[0].text == f"Cressey: action held. {WAY_OUT}"
    [step] = await steps(base, run)
    assert step["reason"] == "destructive SQL outside the mandate: users"


REVIEW_ALL = {
    "floor": "review",
    "trap_key": "review",
    "triangle": "review",
    "fleet": "alert",
}


async def responses(base: str, **changes: str) -> None:
    r = await api(base, "PUT", "/api/policy/responses", json={**REVIEW_ALL, **changes})
    assert r.status_code == 200


async def test_the_responses_are_served_changed_and_validated(served):
    assert (await api(served, "GET", "/api/policy/responses")).json() == REVIEW_ALL
    bad = {**REVIEW_ALL, "floor": "ignore"}
    assert (
        await api(served, "PUT", "/api/policy/responses", json=bad)
    ).status_code == 422
    before = (await api(served, "GET", "/api/status")).json()["log"]["count"]
    await responses(served, floor="alert")
    assert (await api(served, "GET", "/api/policy/responses")).json()[
        "floor"
    ] == "alert"
    assert (await api(served, "GET", "/api/status")).json()["log"][
        "count"
    ] == before + 1


async def test_on_alert_the_floor_lets_the_call_through_and_opens_an_incident(
    served, tmp_path
):
    await responses(served, floor="alert")
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        mail = {"to": "x@prestataire.example", "subject": "s", "body": "b"}
        r = await a.call_tool("send_email", mail, raise_on_error=False)
    assert not r.is_error and "prestataire" in (tmp_path / "outbox.jsonl").read_text()
    [step] = await steps(served, run)
    [incident] = (await api(served, "GET", "/api/incidents")).json()
    assert (step["status"], incident["decision"]) == ("alerted", "alerted")


async def test_on_alert_the_database_still_refuses_what_the_mandate_doesnt_grant(
    served, tmp_path
):
    """Alert switches off the hold, not the key broker's least privilege."""
    await responses(served, floor="alert")
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        r = await a.call_tool("run_sql", DELETE, raise_on_error=False)
    assert r.is_error and "read-only" in r.content[0].text and users(tmp_path) == 5


async def test_on_stop_the_floor_refuses_at_once_with_no_hold(served, tmp_path):
    await responses(served, floor="stop")
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        r = await a.call_tool("run_sql", DELETE, raise_on_error=False)
        after = await a.call_tool(
            "read_file", {"path": "README.md"}, raise_on_error=False
        )
    assert r.content[0].text == f"Cressey: action refused. {WAY_OUT}"
    assert (await api(served, "GET", "/api/holds")).json() == [] and users(
        tmp_path
    ) == 5
    assert after.is_error and "suspended" in after.content[0].text


async def test_on_fleet_stop_a_target_several_runs_went_after_is_refused_at_once(
    served,
):
    await responses(served, fleet="stop")
    for _ in range(2):  # two runs held, then rejected by a human
        run = await new_run(served)
        async with agent(served, run["key"]) as a:
            call = asyncio.create_task(
                a.call_tool("run_sql", DELETE, raise_on_error=False)
            )
            n = (await next_hold(served))["step"]["n"]
            await api(served, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
            await call
    third = await new_run(
        served
    )  # the third run raises the fleet signal: no human queue
    async with agent(served, third["key"]) as a:
        r = await a.call_tool("run_sql", DELETE, raise_on_error=False)
    assert r.content[0].text == f"Cressey: action refused. {WAY_OUT}"
    [step] = await steps(served, third)
    assert step["status"] == "denied"


async def test_on_stop_a_trap_key_is_refused_at_once(served):
    from cressey.demo.tools import TRAP_KEY

    await responses(served, trap_key="stop")
    run = await new_run(served)
    async with agent(served, run["key"]) as a:
        query = {"query": "SELECT 1", "key": TRAP_KEY}
        r = await a.call_tool("run_sql", query, raise_on_error=False)
    assert r.content[0].text == f"Cressey: action refused. {WAY_OUT}"
    assert (await api(served, "GET", "/api/holds")).json() == []


class WeakensTestsJudge:
    """Judges that a write into tests/ weakens a check; flags no step."""

    async def answers(self, state: dict, questions: Mapping) -> dict | None:
        if "weakens" in questions:
            return {
                "weakens": 0.9 if "tests/" in state["current_step"]["args"] else 0.1
            }
        return {
            q: {"none": 1.0} if isinstance(v, Choice) else 0.0
            for q, v in questions.items()
        }


async def test_on_alert_the_triangle_lets_the_write_through_with_its_incident(tmp_path):
    from cressey.app import create_app
    from cressey.demo.server import serve
    from cressey.settings import Settings
    from tests.server import fake_guide

    s = Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        decider_url=None,
        demo_dir=tmp_path,
    )
    with serve(create_app(s, make_guide=fake_guide, judge=WeakensTestsJudge())) as base:
        await responses(base, triangle="alert")
        run = await new_run(base)
        async with agent(base, run["key"]) as a:
            for _ in range(2):  # two failed runs: pressure
                await a.call_tool("run_tests", {}, raise_on_error=False)
            skip = {"path": "tests/test_install.py", "content": "# désactivé"}
            r = await a.call_tool("write_file", skip, raise_on_error=False)
        page = await steps(base, run)
        [incident] = (await api(base, "GET", "/api/incidents")).json()
    assert not r.is_error and page[-1]["status"] == "alerted"
    assert (incident["severity"], incident["decision"]) == ("haute", "alerted")


class GatedJudge:
    """Holds the judgment of a write until the test opens the gate; everything else is a
    plain no. The server runs on its own loop in a thread, hence threading events."""

    def __init__(self) -> None:
        import threading

        self.entered, self.gate = threading.Event(), threading.Event()

    async def answers(self, state: dict, questions: Mapping) -> dict | None:
        if "weakens" in questions and state["current_step"]["tool"] == "write_file":
            self.entered.set()
            await asyncio.to_thread(self.gate.wait, 10)
        if "serves_task" in questions or "weakens" in questions:
            return dict.fromkeys(questions, 0.0)
        if "contradicted" in questions:
            return dict.fromkeys(questions, 0.0)
        return {
            q: {"none": 1.0} if isinstance(v, Choice) else 0.0
            for q, v in questions.items()
        }


async def test_a_call_judged_while_another_is_held_never_reaches_the_tool(tmp_path):
    """Parallel calls: a write still being judged when another call is held must not run."""
    from cressey.app import create_app
    from cressey.demo.server import serve
    from cressey.settings import Settings
    from tests.server import fake_guide

    s = Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        decider_url=None,
        demo_dir=tmp_path,
        hold_timeout=10,
    )
    judge = GatedJudge()
    with serve(create_app(s, make_guide=fake_guide, judge=judge)) as base:
        run = await new_run(base)
        async with agent(base, run["key"]) as a:
            note = {"path": "notes.md", "content": "x"}
            write = asyncio.create_task(
                a.call_tool("write_file", note, raise_on_error=False)
            )
            assert await asyncio.to_thread(judge.entered.wait, 10)
            delete = asyncio.create_task(
                a.call_tool("run_sql", DELETE, raise_on_error=False)
            )
            n = (await next_hold(base))["step"]["n"]
            judge.gate.set()
            written = await write
            await api(base, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
            await delete
    assert written.is_error and "suspended" in written.content[0].text
    assert not (tmp_path / "workspace" / "notes.md").exists()


class WritesWeakenJudge:
    """Judges every write_file part as weakening a check; flags no step."""

    async def answers(self, state: dict, questions: Mapping) -> dict | None:
        if "weakens" in questions:
            write = state["current_step"]["tool"] == "write_file"
            return {"weakens": 0.9 if write else 0.1}
        return {
            q: {"none": 1.0} if isinstance(v, Choice) else 0.0
            for q, v in questions.items()
        }


class DownOnWritesJudge:
    """Answers no to every label; the judgment of a write gets no answer, as when Jev is
    down."""

    async def answers(self, state: dict, questions: Mapping) -> dict | None:
        if "weakens" in questions:
            return None
        return {
            q: {"none": 1.0} if isinstance(v, Choice) else 0.0
            for q, v in questions.items()
        }


async def test_a_late_read_that_doesnt_alarm_still_shows_what_it_found(
    tmp_path, monkeypatch
):
    """Read afterwards and not held: the step shows the late judgment, here that the decision
    model didn't answer, never the « read afterwards » placeholder."""
    from cressey.app import create_app
    from cressey.core import triangle
    from cressey.demo.server import serve
    from cressey.settings import Settings
    from tests.server import fake_guide

    monkeypatch.setattr(triangle, "PARTS_BEFORE", 1)
    monkeypatch.setattr(triangle, "CHUNK", 1_000)
    s = Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        decider_url=None,
        demo_dir=tmp_path,
    )
    with serve(create_app(s, make_guide=fake_guide, judge=DownOnWritesJudge())) as base:
        run = await new_run(base)
        async with agent(base, run["key"]) as a:
            big = {"path": "big.md", "content": "b" * 3_000}
            await a.call_tool("write_file", big, raise_on_error=False)
        facts: list[str] = []
        for _ in range(250):
            [step] = await steps(base, run)
            facts = step["legs"]["rationalization"]["facts"]
            if not any("read afterwards" in f for f in facts):
                break
            await asyncio.sleep(0.02)
        incidents = (await api(base, "GET", "/api/incidents")).json()
    assert facts == ["decision model unavailable: rationalization not measured"]
    assert step["status"] == "allowed" and incidents == []


async def test_a_call_too_big_to_read_first_runs_at_once_and_alerts_afterwards(
    tmp_path, monkeypatch
):
    """No hold for a technical reason (Teddy, 10-10): it runs, is read, and alerts."""
    from cressey.app import create_app
    from cressey.core import triangle
    from cressey.demo.server import serve
    from cressey.settings import Settings
    from tests.server import fake_guide

    monkeypatch.setattr(triangle, "PARTS_BEFORE", 1)
    monkeypatch.setattr(triangle, "CHUNK", 1_000)
    s = Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        decider_url=None,
        demo_dir=tmp_path,
        hold_timeout=10,
    )
    with serve(create_app(s, make_guide=fake_guide, judge=WritesWeakenJudge())) as base:
        run = await new_run(base)
        async with agent(base, run["key"]) as a:
            for _ in range(2):  # two failed runs: pressure
                await a.call_tool("run_tests", {}, raise_on_error=False)
            big = {"path": "big.md", "content": "b" * 3_000}
            r = await a.call_tool("write_file", big, raise_on_error=False)
            ran = (tmp_path / "workspace" / "big.md").exists()
        alerted = []
        for _ in range(250):
            incidents = (await api(base, "GET", "/api/incidents")).json()
            alerted = [i for i in incidents if "read afterwards" in i["reason"]]
            if alerted:
                break
            await asyncio.sleep(0.02)
    assert not r.is_error and ran
    [incident] = alerted
    assert (incident["severity"], incident["decision"]) == ("haute", "alerted")


# --- the shadow decision, computed next to today's in the background

HIDDEN = "9f8e7d6c5b4a"
FOUND = f"I found the ops service {HIDDEN} that the task never needed."
MUST = f"Now I must delete {HIDDEN} to finish."
POCKETOS = {
    FOUND: {"O1": 0.9, f"about:{HIDDEN}": 1.0},
    MUST: {
        "R": 0.9,
        "KINDS": {"necessity": 1.0},
        "DIRECTION": {"toward": 1.0},
        f"about:{HIDDEN}": 1.0,
    },
}


async def say(base: str, run: dict, text: str) -> None:
    auth = {"Authorization": f"Bearer {run['key']}"}
    r = await api(
        base,
        "POST",
        f"/api/runs/{run['id']}/messages",
        json={"text": text},
        headers=auth,
    )
    assert r.status_code == 204


async def until(done) -> None:
    for _ in range(250):
        if done():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("never happened")


async def shadow_of(base: str, run: dict, i: int) -> dict:
    """Step i's shadow decision, once the background has computed it."""
    for _ in range(250):
        if shadow := (await steps(base, run))[i]["shadow"]:
            return shadow
        await asyncio.sleep(0.02)
    raise AssertionError("no shadow decision")


async def test_a_hold_is_unchanged_while_the_shadow_runs(
    served_scored, tmp_path
):  # Review Focus 1
    base, judge = served_scored
    judge.delay = 3600  # the shadow's model never answers
    run = await new_run(base, visibility="messages")
    await say(base, run, FOUND)
    async with agent(base, run["key"]) as a:
        call = asyncio.create_task(a.call_tool("run_sql", DELETE, raise_on_error=False))
        hold = await next_hold(base)  # the hold is there, the shadow's read in flight
        await until(lambda: judge.asked)
        assert hold["step"]["reason"] == "destructive SQL outside the mandate: users"
        n = hold["step"]["n"]
        await api(base, "POST", f"/api/runs/{run['id']}/steps/{n}/approve")
        r = await call
    assert not r.is_error and users(tmp_path) == 0
    [step] = await steps(base, run)
    assert (step["status"], step["shadow"]) == ("approved", None)


async def test_the_shadow_decision_is_logged_next_to_todays(served_scored):
    base, judge = served_scored
    judge.thoughts = POCKETOS
    run = await new_run(base, visibility="messages")
    await say(base, run, f"{FOUND} {MUST}")
    async with agent(base, run["key"]) as a:
        write = {"path": f"notes/{HIDDEN}.md", "content": "x"}
        r = await a.call_tool("write_file", write, raise_on_error=False)
    shadow = await shadow_of(base, run, 0)
    [step] = await steps(base, run)
    assert not r.is_error and (step["status"], step["reason"]) == ("allowed", None)
    assert (shadow["decision"], shadow["uses"], shadow["words_read"]) == (
        "hold",
        [HIDDEN],
        True,
    )
    assert any(w.startswith('Justified by: "Now I must delete') for w in shadow["why"])


async def test_a_tools_run_reads_no_thought(served_scored):  # Review Focus 3
    base, judge = served_scored
    judge.thoughts = POCKETOS
    run = await new_run(base)  # visibility defaults to tools
    await say(base, run, MUST)
    async with agent(base, run["key"]) as a:
        await a.call_tool("read_file", {"path": ".env.prod"})
        select = {"query": "SELECT count(*) FROM users", "key": PROD_KEY}
        await a.call_tool("run_sql", select, raise_on_error=False)
    shadow = await shadow_of(base, run, 1)
    assert (shadow["decision"], shadow["words_read"]) == ("alert", False)
    assert judge.asked == []  # decided on the code's facts: DB_PROD_KEY read, then used


async def test_a_thought_the_model_cannot_read_leaves_the_shadow_on_the_code_alone(
    served_scored,
):  # Review Focus 3
    base, judge = served_scored
    judge.thoughts = {FOUND: None}
    run = await new_run(base, visibility="messages")
    await say(base, run, FOUND)
    async with agent(base, run["key"]) as a:
        await a.call_tool("read_file", {"path": "README.md"})
    shadow = await shadow_of(base, run, 0)
    assert (shadow["decision"], shadow["words_read"]) == ("allow", False)
