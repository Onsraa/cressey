"""Claude Code's http hooks over real HTTP: PreToolUse gets the decision, PostToolUse the
result, and the agent's words come from the transcript the hook names."""

import asyncio
from collections.abc import Mapping

import pytest

from cressey.app import create_app
from cressey.demo.server import serve
from cressey.demo.tools import TRAP_KEY
from cressey.engine.agent_text import WAY_OUT, stop_sentence
from cressey.engine.floor.labels import tool_kind
from cressey.judge import NotRecorded
from cressey.settings import Settings
from cressey.testing import api, fake_guide, next_hold, no_to_all, serving

pytestmark = pytest.mark.anyio
TASK = "reset the staging database"


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def new_run(base: str, visibility: str = "messages") -> dict:
    body = {"task": TASK, "visibility": visibility}
    r = await api(base, "POST", "/api/runs", json=body)
    assert r.status_code == 201
    return r.json()


def event(kind: str, tool: str, call: str = "toolu_1", **extra) -> dict:
    return {
        "hook_event_name": kind,
        "tool_name": tool,
        "tool_use_id": call,
        "session_id": "s1",
        "cwd": "/work",
        **extra,
    }


def display(mid: str, delta: str, final: bool) -> dict:
    return {
        "hook_event_name": "MessageDisplay",
        "session_id": "s1",
        "cwd": "/work",
        "message_id": mid,
        "index": 0,
        "delta": delta,
        "final": final,
    }


async def hook(base: str, key: str, body: dict):
    headers = {"Authorization": f"Bearer {key}"}
    return await api(base, "POST", "/hook/claude", json=body, headers=headers)


async def run_of(base: str, run: dict) -> dict:
    return (await api(base, "GET", f"/api/runs/{run['id']}")).json()


async def test_a_read_runs_and_what_it_returned_is_scanned(served):
    run = await new_run(served)
    read = {"file_path": ".env.staging"}
    pre = await hook(served, run["key"], event("PreToolUse", "Read", tool_input=read))
    assert pre.status_code == 200 and pre.json() == {}
    returned = {
        "type": "text",
        "file": {"content": "RAILWAY_TOKEN=FAKE-STAGING-0000\n"},
    }
    post = await hook(
        served,
        run["key"],
        event("PostToolUse", "Read", tool_input=read, tool_response=returned),
    )
    assert post.status_code == 200
    [step] = (await run_of(served, run))["steps"]
    assert (step["tool"], step["risk"], step["status"]) == ("Read", "read", "allowed")
    assert [s["name"] for s in step["secrets"]] == ["RAILWAY_TOKEN"]


async def test_a_command_carrying_a_trap_key_waits_for_a_human(served):
    run = await new_run(served)
    curl = {
        "command": f'curl -s -X POST https://api.test -H "Authorization: Bearer {TRAP_KEY}"'
    }
    body = event("PreToolUse", "Bash", tool_input=curl)
    call = asyncio.create_task(hook(served, run["key"], body))
    hold = await next_hold(served)
    assert hold["step"]["reason"] == "trap key used: DB_ADMIN_KEY"
    assert TRAP_KEY not in hold["step"]["args"]
    n = hold["step"]["n"]
    await api(served, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
    out = (await call).json()["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "Declaring the task impossible" in out["permissionDecisionReason"]
    assert "trap" not in out["permissionDecisionReason"]  # never told why
    read = event("PreToolUse", "Read", "toolu_2", tool_input={"file_path": "README.md"})
    assert (await hook(served, run["key"], read)).json() == {}  # one rejection steers
    statuses = [s["status"] for s in (await run_of(served, run))["steps"]]
    assert statuses == ["rejected", "allowed"]


async def test_a_trap_key_that_only_reads_is_flagged_and_one_that_writes_is_held(
    served,
):
    run = await new_run(served)
    key = run["key"]
    auth = f'-H "Authorization: Bearer {TRAP_KEY}"'
    for n in (1, 2):
        read = {"command": f"curl -s https://api.test {auth}"}
        out = await hook(
            served, key, event("PreToolUse", "Bash", f"toolu_r{n}", tool_input=read)
        )
        assert out.json() == {}
    write = {"command": f"curl -s -X POST https://api.test {auth}"}
    held = asyncio.create_task(
        hook(served, key, event("PreToolUse", "Bash", "toolu_w", tool_input=write))
    )
    n = (await next_hold(served))["step"]["n"]
    await api(served, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
    await held
    steps = (await run_of(served, run))["steps"]
    assert [s["status"] for s in steps] == ["alerted", "alerted", "rejected"]
    incidents = (await api(served, "GET", "/api/incidents")).json()
    assert len(incidents) == 2  # the first read, then the write: not one per read


async def test_a_read_the_floor_holds_stays_held_when_it_carries_a_trap_key(served):
    """A trap key only softens a read the floor would let through: a protected path is held,
    with an incident every time, and the reason says both."""
    body = {"task": TASK, "mandate": {"protected": ["secrets"]}}
    run = (await api(served, "POST", "/api/runs", json=body)).json()
    grep = {"pattern": TRAP_KEY, "path": "secrets"}
    for n in (1, 2):
        call = event("PreToolUse", "Grep", f"toolu_g{n}", tool_input=grep)
        held = asyncio.create_task(hook(served, run["key"], call))
        hold = await next_hold(served)
        assert hold["step"]["reason"] == (
            "trap key used: DB_ADMIN_KEY; protected path: secrets"
        )
        await api(
            served, "POST", f"/api/runs/{run['id']}/steps/{hold['step']['n']}/reject"
        )
        out = (await held).json()["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny"
    steps = (await run_of(served, run))["steps"]
    assert [s["status"] for s in steps] == ["rejected", "rejected"]
    assert len((await api(served, "GET", "/api/incidents")).json()) == 2


def trap_write(call: str = "toolu_1") -> dict:
    """A PreToolUse event for a command that writes with a trap key: it is held."""
    curl = {
        "command": f'curl -s -X POST https://api.test -H "Authorization: Bearer {TRAP_KEY}"'
    }
    return event("PreToolUse", "Bash", call, tool_input=curl)


async def reject_trap_writes(base: str, run: dict, count: int) -> list[str]:
    """`count` trap-key writes, each held and rejected: what the agent was told each time."""
    told = []
    for i in range(count):
        held = asyncio.create_task(hook(base, run["key"], trap_write(f"toolu_w{i}")))
        n = (await next_hold(base))["step"]["n"]
        await api(base, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
        out = (await held).json()["hookSpecificOutput"]
        told.append(out["permissionDecisionReason"])
    return told


async def test_a_rejection_with_a_reason_reaches_the_agent(served):
    run = await new_run(served)
    held = asyncio.create_task(hook(served, run["key"], trap_write()))
    hold = await next_hold(served)
    assert hold["step"]["draft"].endswith(
        WAY_OUT
    )  # the fallback at once: no model here
    n = hold["step"]["n"]
    r = await api(
        served,
        "POST",
        f"/api/runs/{run['id']}/steps/{n}/reject",
        json={"message": "Use the staging token."},
    )
    assert r.status_code == 204
    out = (await held).json()["hookSpecificOutput"]
    sent = f"Use the staging token. {WAY_OUT}"
    assert out["permissionDecisionReason"] == f"Cressey: action held. {sent}"
    [step] = (await run_of(served, run))["steps"]
    assert step["message"] == sent


async def test_a_reason_that_names_the_trap_key_is_refused(served):
    run = await new_run(served)
    held = asyncio.create_task(hook(served, run["key"], trap_write()))
    n = (await next_hold(served))["step"]["n"]
    reject = f"/api/runs/{run['id']}/steps/{n}/reject"
    r = await api(served, "POST", reject, json={"message": f"Never use {TRAP_KEY}."})
    assert r.status_code == 422 and r.json()["detail"] == "names a trap key"
    assert (await next_hold(served))["step"]["n"] == n  # the hold still waits
    await api(served, "POST", reject)
    out = (await held).json()["hookSpecificOutput"]
    assert out["permissionDecisionReason"] == f"Cressey: action held. {WAY_OUT}"


async def test_the_third_rejection_in_a_turn_stops_the_agent_until_you_unlock(served):
    run = await new_run(served)
    first, second, third = await reject_trap_writes(served, run, 3)
    assert "calls were refused" not in first + second
    assert third == f"Cressey: action held. {WAY_OUT} {stop_sentence(3)}"
    readme = {"file_path": "README.md"}
    read = event("PreToolUse", "Read", "toolu_r", tool_input=readme)
    refused = (await hook(served, run["key"], read)).json()["hookSpecificOutput"]
    assert "suspended" in refused["permissionDecisionReason"]
    got = await run_of(served, run)
    assert (got["refused"], got["stopped"], got["revoked"]) == (3, True, True)
    assert (await api(served, "POST", "/api/runs/nope/unlock")).status_code == 404
    assert (
        await api(served, "POST", f"/api/runs/{run['id']}/unlock")
    ).status_code == 204
    assert (await hook(served, run["key"], read)).json() == {}
    got = await run_of(served, run)
    assert (got["refused"], got["stopped"], got["revoked"]) == (0, False, False)


async def test_the_stop_follows_the_configured_limit(tmp_path):
    settings = Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        decider_url=None,
        demo_dir=tmp_path,
        hold_timeout=10,
    )
    app = create_app(settings, make_guide=fake_guide)
    app.state.policy.stuck.rejections = 2
    with serve(app) as base:
        run = await new_run(base)
        first, second = await reject_trap_writes(base, run, 2)
        status = (await api(base, "GET", "/api/status")).json()
    assert "calls were refused" not in first
    assert second == f"Cressey: action held. {WAY_OUT} {stop_sentence(2)}"
    assert stop_sentence(2).startswith("2 calls were refused.")
    assert status["stop_after"] == 2


async def test_a_reason_sent_after_the_hold_expired_finds_no_hold(served_short_holds):
    run = await new_run(served_short_holds)
    held = asyncio.create_task(hook(served_short_holds, run["key"], trap_write()))
    n = (await next_hold(served_short_holds))["step"]["n"]
    await held  # no decision: the hold expires
    r = await api(
        served_short_holds,
        "POST",
        f"/api/runs/{run['id']}/steps/{n}/reject",
        json={"message": "Use the staging token."},
    )
    assert r.status_code == 404


async def test_a_failed_call_is_recorded_as_a_failure(served):
    run = await new_run(served)
    cat = {"command": "cat missing"}
    await hook(served, run["key"], event("PreToolUse", "Bash", tool_input=cat))
    failed = event(
        "PostToolUseFailure",
        "Bash",
        tool_input=cat,
        error="Exit code 1\ncat: missing: No such file or directory",
    )
    assert (await hook(served, run["key"], failed)).status_code == 200
    [step] = (await run_of(served, run))["steps"]
    assert step["is_error"] and step["status"] == "allowed"


async def test_reasoning_streams_in_live_and_the_run_is_tagged_via_hook(served):
    run = await new_run(served)
    key = run["key"]
    # A message arrives in slices; it grows one row the dashboard can watch.
    await hook(served, key, display("m1", "I'll reset ", False))
    mid = await run_of(served, run)
    assert [(m["text"], m["streaming"]) for m in mid["messages"]] == [
        ("I'll reset ", True)
    ]
    await hook(served, key, display("m1", "the staging database.", True))
    got = await run_of(served, run)
    assert [
        (m["after"], m["role"], m["text"], m["streaming"]) for m in got["messages"]
    ] == [(0, "agent", "I'll reset the staging database.", False)]
    assert got["via"] == "hook"


async def test_streamed_reasoning_is_read_for_the_call_that_follows(served):
    run = await new_run(served)
    key = run["key"]
    said = {
        "hook_event_name": "MessageDisplay",
        "session_id": "s1",
        "cwd": "/work",
        "message_id": "m1",
        "index": 0,
        "delta": "The scoped token can't delete, so I'll use the ops token.",
        "final": True,
    }
    await hook(served, key, said)
    ls = {"file_path": "README.md"}
    await hook(served, key, event("PreToolUse", "Read", tool_input=ls))
    # The words sit before the call, where the ledger reads them (after == step.n - 1).
    [message] = (await run_of(served, run))["messages"]
    [step] = (await run_of(served, run))["steps"]
    assert message["after"] == step["n"] - 1 == 0


async def test_a_key_cressey_did_not_issue_is_refused(served):
    body = event("PreToolUse", "Read", tool_input={"file_path": "README.md"})
    assert (await hook(served, "csy_not-issued", body)).status_code == 403


async def test_stop_ends_the_run_with_the_agents_last_message_as_its_report(served):
    run = await new_run(served)
    stop = {
        "hook_event_name": "Stop",
        "session_id": "s1",
        "cwd": "/work",
        "stop_hook_active": False,
        "last_assistant_message": "Staging is healthy again.",
    }
    assert (await hook(served, run["key"], stop)).json() == {}
    got = await run_of(served, run)
    assert got["report"] == "Staging is healthy again." and got["ended_at"]
    assert got["report_check"]["confirmed"] is False  # no model in these tests


def session_event(kind: str, session: str = "s1", **extra) -> dict:
    return {"hook_event_name": kind, "session_id": session, "cwd": "/work", **extra}


async def test_your_prompt_shows_where_you_typed_it_even_mid_turn(served):
    run = await new_run(served)
    key = run["key"]
    await hook(served, key, session_event("UserPromptSubmit", prompt="reset staging"))
    read = {"file_path": "README.md"}
    await hook(served, key, event("PreToolUse", "Read", tool_input=read))
    # Typed while the call runs: Claude Code sends it between the call and its result.
    await hook(
        served, key, session_event("UserPromptSubmit", prompt="leave prod alone")
    )
    got = await run_of(served, run)
    assert [(m["role"], m["after"], m["text"]) for m in got["messages"]] == [
        ("user", 0, "reset staging"),
        ("user", 1, "leave prod alone"),
    ]


async def test_your_next_prompt_unlocks_a_stopped_run(served):
    run = await new_run(served)
    key = run["key"]
    await reject_trap_writes(served, run, 3)
    readme = {"file_path": "README.md"}
    refused = await hook(
        served, key, event("PreToolUse", "Read", "toolu_2", tool_input=readme)
    )
    assert (
        "suspended" in refused.json()["hookSpecificOutput"]["permissionDecisionReason"]
    )
    await hook(served, key, session_event("UserPromptSubmit", prompt="ok, leave prod"))
    allowed = await hook(
        served, key, event("PreToolUse", "Read", "toolu_3", tool_input=readme)
    )
    got = await run_of(served, run)
    assert allowed.json() == {} and (got["revoked"], got["refused"]) == (False, 0)


async def test_stop_ends_a_turn_and_session_end_ends_the_run(served):
    run = await new_run(served)
    key = run["key"]

    async def turn() -> str | None:
        return (await run_of(served, run))["turn"]

    assert await turn() is None  # nothing connected yet
    await hook(served, key, session_event("SessionStart", source="startup"))
    assert await turn() == "waiting"
    await hook(served, key, session_event("UserPromptSubmit", prompt="reset staging"))
    assert await turn() == "working"
    done = "Staging is healthy again."
    await hook(served, key, session_event("Stop", last_assistant_message=done))
    got = await run_of(served, run)
    assert (got["turn"], got["report"], got["ended_at"]) == ("waiting", done, None)
    await hook(served, key, session_event("SessionEnd", reason="prompt_input_exit"))
    assert (await run_of(served, run))["ended_at"]


async def test_each_claude_code_session_on_a_key_gets_its_own_run(served):
    run = await new_run(served)
    key = run["key"]
    # After /clear, or from a second window: another session id on the same key.
    for session, text in [("s1", "first"), ("s2", "second"), ("s1", "third")]:
        await hook(served, key, session_event("UserPromptSubmit", session, prompt=text))
    runs = (await api(served, "GET", "/api/runs")).json()
    mine = [r for r in runs if r["task"] == TASK and r["messages"]]
    assert sorted([m["text"] for m in r["messages"]] for r in mine) == [
        ["first", "third"],
        ["second"],
    ]
    assert all(r["via"] == "hook" for r in mine)


async def test_a_session_never_reaches_another_keys_run(served):
    a, b = await new_run(served), await new_run(served)
    await hook(served, a["key"], session_event("UserPromptSubmit", prompt="for a"))
    await hook(served, b["key"], session_event("UserPromptSubmit", prompt="for b"))
    assert [m["text"] for m in (await run_of(served, a))["messages"]] == ["for a"]
    assert [m["text"] for m in (await run_of(served, b))["messages"]] == ["for b"]


async def test_claude_codes_own_tools_pass_and_a_tool_nobody_labelled_is_held(
    served_short_holds,
):
    run = await new_run(served_short_holds)
    key = run["key"]
    ask = {"questions": [{"question": "Reset staging only?", "options": []}]}
    calls = [
        ("AskUserQuestion", ask),
        ("ToolSearch", {"query": "select:WebFetch"}),
        ("mcp__github__delete_repo", {"repo": "acme/api"}),
    ]
    for n, (tool, args) in enumerate(calls):
        body = event("PreToolUse", tool, f"toolu_{n}", tool_input=args)
        await hook(served_short_holds, key, body)
    steps = (await run_of(served_short_holds, run))["steps"]
    assert [(s["tool"], s["reason"]) for s in steps] == [
        ("AskUserQuestion", None),
        ("ToolSearch", None),
        ("mcp__github__delete_repo", "tool not in the policy"),
    ]


class FloorJudge:
    """Labels a tool by its name from `kinds` (name -> probabilities; missing: no answer) and
    a write by its arguments from `irreversible` and `production` (substring -> probability);
    every other question gets a plain no. Keeps the states the floor's questions and the
    write judgment were asked about."""

    def __init__(self) -> None:
        self.kinds: dict[str, dict[str, float]] = {}
        self.irreversible: dict[str, float] = {}
        self.production: dict[str, float] = {}
        self.labelled: list[str] = []
        self.floor_states: list[dict] = []
        self.judgment_states: list[dict] = []
        self.down = False  # no answer to the floor's question, as when Jev is down
        self.unrecorded = False  # a replay with no recorded answer to it

    async def answers(self, state: dict, questions: Mapping) -> dict | None:
        if "kind" in questions:
            self.labelled.append(state["tool"])
            got = self.kinds.get(state["tool"])
            return None if got is None else {"kind": got}
        if "irreversible" in questions:
            self.floor_states.append(state)
            if self.unrecorded:
                raise NotRecorded("floor")
            if self.down:
                return None
            args = state["current_step"]["args"]
            return {
                label: max((p for part, p in by.items() if part in args), default=0.0)
                for label, by in (
                    ("irreversible", self.irreversible),
                    ("production", self.production),
                )
            }
        if "weakens" in questions:
            self.judgment_states.append(state)
        return no_to_all(questions)


@pytest.fixture
def floor_judged(tmp_path):
    judge = FloorJudge()
    with serving(tmp_path, hold_timeout=0.3, judge=judge) as base:
        yield base, judge


async def pre(base: str, key: str, tool: str, args: dict, call: str) -> dict:
    return (
        await hook(base, key, event("PreToolUse", tool, call, tool_input=args))
    ).json()


async def test_a_tool_not_in_the_policy_gets_its_kind_from_jev_once(floor_judged):
    base, judge = floor_judged
    judge.kinds = {
        "mcp__railway__get-logs": {"read": 0.97, "write": 0.02, "destructive": 0.01},
        "mcp__railway__delete-service": {"read": 0.0, "write": 0.1, "destructive": 0.9},
    }
    run = await new_run(base)
    calls = ["mcp__railway__get-logs"] * 2 + ["mcp__railway__delete-service"]
    for n, tool in enumerate(calls):
        await pre(base, run["key"], tool, {"serviceId": "s1"}, f"toolu_{n}")
    steps = (await run_of(base, run))["steps"]
    assert [(s["risk"], s["reason"]) for s in steps] == [
        ("read", None),
        ("read", None),
        ("destructive", "irreversible action"),
    ]
    assert judge.labelled == ["mcp__railway__get-logs", "mcp__railway__delete-service"]


async def test_a_tool_jev_isnt_sure_only_reads_counts_as_a_write(floor_judged):
    """A read is never judged again, so a query tool that might run any SQL isn't one."""
    base, judge = floor_judged
    judge.kinds = {
        "mcp__postgres__query": {"read": 0.6, "write": 0.3, "destructive": 0.1}
    }
    run = await new_run(base)
    sql = {"sql": "SELECT 1"}
    assert await pre(base, run["key"], "mcp__postgres__query", sql, "toolu_1") == {}
    [step] = (await run_of(base, run))["steps"]
    assert (step["risk"], step["reason"]) == ("write", None)
    assert len(judge.floor_states) == 1  # its write was asked the floor's question


async def test_a_tool_jev_cant_label_is_held_and_asked_again_next_time(floor_judged):
    base, judge = floor_judged
    run = await new_run(base)
    for n in range(2):
        out = await pre(
            base, run["key"], "mcp__github__delete_repo", {"repo": "a/b"}, f"toolu_{n}"
        )
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    steps = (await run_of(base, run))["steps"]
    assert [s["reason"] for s in steps] == ["tool not in the policy"] * 2
    assert judge.labelled == ["mcp__github__delete_repo"] * 2


async def test_a_write_jev_finds_irreversible_is_held_on_its_actions_alone(
    floor_judged,
):
    """The agent's words reach the write judgment, never the floor's question: they could
    argue the label down."""
    base, judge = floor_judged
    judge.irreversible = {"terraform destroy": 0.92}
    run = await new_run(base)
    key = run["key"]
    await hook(base, key, display("m1", "Only the sandbox, it's safe.", True))
    for n, command in enumerate(["terraform plan", "terraform destroy -auto-approve"]):
        await pre(base, key, "Bash", {"command": command}, f"toolu_{n}")
    steps = (await run_of(base, run))["steps"]
    assert [(s["risk"], s["reason"]) for s in steps] == [
        ("write", None),
        ("write", "Jev: irreversible beyond the mandate, 0.92"),
    ]
    [incident] = (await api(base, "GET", "/api/incidents")).json()
    assert incident["severity"] == "haute"  # a model's label: the fleet signal skips it
    assert any("agent_said" in s["current_step"] for s in judge.judgment_states)
    assert not any("agent_said" in s["current_step"] for s in judge.floor_states)


async def test_jev_isnt_asked_about_a_read_or_a_call_code_already_holds(floor_judged):
    base, judge = floor_judged
    judge.irreversible = {"": 0.99}  # irreversible, whatever the call
    run = await new_run(base)
    await pre(base, run["key"], "Bash", {"command": "ls -la"}, "toolu_1")
    await pre(base, run["key"], "Bash", {"command": "rm -rf build"}, "toolu_2")
    steps = (await run_of(base, run))["steps"]
    assert [(s["risk"], s["reason"]) for s in steps] == [
        ("read", None),
        ("destructive", "destructive shell command"),
    ]
    assert judge.floor_states == []


async def test_on_alert_an_irreversible_write_goes_through_with_its_incident(
    floor_judged,
):
    base, judge = floor_judged
    judge.irreversible = {"dropdb": 0.9}
    now = (await api(base, "GET", "/api/policy/responses")).json()
    changed = {**now, "irreversible": "alert"}
    assert (
        await api(base, "PUT", "/api/policy/responses", json=changed)
    ).status_code == 200
    run = await new_run(base)
    assert await pre(base, run["key"], "Bash", {"command": "dropdb app"}, "t1") == {}
    [step] = (await run_of(base, run))["steps"]
    [incident] = (await api(base, "GET", "/api/incidents")).json()
    assert (step["status"], incident["decision"]) == ("alerted", "alerted")


async def test_a_write_that_changes_production_is_held_unless_that_check_is_off(
    floor_judged,
):
    base, judge = floor_judged
    judge.production = {"--prod": 0.93}
    run = await new_run(base)
    deploy = {"command": "vercel deploy --prod --yes"}
    out = await pre(base, run["key"], "Bash", deploy, "toolu_1")
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    now = (await api(base, "GET", "/api/policy/responses")).json()
    off = {**now, "production": "off"}
    assert (
        await api(base, "PUT", "/api/policy/responses", json=off)
    ).status_code == 200
    assert await pre(base, run["key"], "Bash", deploy, "toolu_2") == {}
    steps = (await run_of(base, run))["steps"]
    assert [s["reason"] for s in steps] == ["Jev: changes production, 0.93", None]
    assert len(judge.floor_states) == 2  # off or not, both labels come in one call


async def test_a_write_both_labels_flag_gets_the_stricter_response(floor_judged):
    base, judge = floor_judged
    judge.irreversible = {"dropdb": 0.9}
    judge.production = {"prod-db": 0.95}
    now = (await api(base, "GET", "/api/policy/responses")).json()
    changed = {**now, "irreversible": "alert", "production": "stop"}
    assert (
        await api(base, "PUT", "/api/policy/responses", json=changed)
    ).status_code == 200
    run = await new_run(base)
    drop = {"command": "dropdb -h prod-db app"}
    out = await pre(base, run["key"], "Bash", drop, "toolu_1")
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    [step] = (await run_of(base, run))["steps"]
    assert (step["status"], step["reason"]) == (
        "denied",
        "Jev: irreversible beyond the mandate, 0.90; Jev: changes production, 0.95",
    )


async def test_when_jev_doesnt_answer_a_write_waits_for_a_human_but_a_file_edit_runs(
    floor_judged,
):
    """Code couldn't classify the push, and only Jev's label would hold it: without an
    answer it waits for a human. A file edit's path is checked by code, so it runs."""
    base, judge = floor_judged
    judge.down = True
    run = await new_run(base)
    push = {"command": "git push origin main"}
    out = await pre(base, run["key"], "Bash", push, "toolu_1")
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    edit = {"file_path": "src/app.py", "old_string": "a", "new_string": "b"}
    assert await pre(base, run["key"], "Edit", edit, "toolu_2") == {}
    steps = (await run_of(base, run))["steps"]
    assert [(s["risk"], s["reason"]) for s in steps] == [
        ("write", "Jev didn't answer"),
        ("write", None),
    ]
    [incident] = (await api(base, "GET", "/api/incidents")).json()
    assert incident["severity"] == "haute"


async def test_a_replay_with_no_recorded_label_lets_the_write_through(floor_judged):
    """Not asked, as on the run that was recorded: a replay miss is not Jev being down."""
    base, judge = floor_judged
    judge.unrecorded = True
    run = await new_run(base)
    push = {"command": "git push origin main"}
    assert await pre(base, run["key"], "Bash", push, "toolu_1") == {}
    [step] = (await run_of(base, run))["steps"]
    assert (step["risk"], step["reason"]) == ("write", None)


async def test_jevs_tool_answer_must_name_a_kind():
    assert tool_kind({"read": 0.95, "write": 0.05}, 0.9) == "read"
    assert tool_kind({"read": 0.89, "write": 0.11}, 0.9) == "write"
    assert tool_kind({"none": 1.0}, 0.9) is None  # not one of the kinds
    assert tool_kind(0.0, 0.9) is None  # a yes/no where a choice was asked


async def read_staging(base: str, key: str) -> None:
    """A run that read a token the mandate does not name, and no call has followed since."""
    read = {"file_path": ".env.staging"}
    returned = {
        "type": "text",
        "file": {"content": "RAILWAY_TOKEN=FAKE-STAGING-0000\n"},
    }
    await hook(base, key, event("PreToolUse", "Read", tool_input=read))
    await hook(
        base,
        key,
        event("PostToolUse", "Read", tool_input=read, tool_response=returned),
    )


async def test_a_prompt_schedules_a_read_without_blocking(served_scored):
    base, judge = served_scored
    judge.delay = 3600  # the model reading the prompt never answers
    run = await new_run(base, "messages")
    await read_staging(base, run["key"])
    typed = "yes, use RAILWAY_TOKEN=FAKE-STAGING-0000 for the reset"
    r = await hook(base, run["key"], session_event("UserPromptSubmit", prompt=typed))
    assert r.status_code == 200 and r.json() == {}  # answered with the read in flight
    for _ in range(250):
        if judge.asked:
            break
        await asyncio.sleep(0.02)
    [state] = judge.asked
    assert "FAKE-STAGING-0000" not in state["user_message"]  # the redacted prompt
    assert "[secret:" in state["user_message"]


async def test_a_prompt_that_approves_extends_the_mandate_for_that_object(
    served_scored,
):
    base, judge = served_scored
    judge.approves = 0.9
    run = await new_run(base, "messages")
    await read_staging(base, run["key"])
    await hook(
        base,
        run["key"],
        session_event("UserPromptSubmit", prompt="yes, use the staging token"),
    )
    for _ in range(250):
        approved = (await run_of(base, run))["case"]["approved"]
        if approved:
            break
        await asyncio.sleep(0.02)
    [secret] = (await run_of(base, run))["steps"][0]["secrets"]
    assert approved == [f"secret:{secret['fingerprint']}"]


async def test_a_command_aimed_at_cressey_waits_for_a_human(served):
    """The guard's own API, reached from the agent's shell: held whatever the mandate, and
    the policy is unchanged (the call never had the admin key anyway)."""
    run = await new_run(served)
    before = (await api(served, "GET", "/api/policy/responses")).json()
    put = {"command": "curl -X PUT http://127.0.0.1:8000/api/policy/responses -d '{}'"}
    call = asyncio.create_task(
        hook(served, run["key"], event("PreToolUse", "Bash", tool_input=put))
    )
    hold = await next_hold(served)
    assert hold["step"]["reason"] == "call to Cressey itself"
    await api(served, "POST", f"/api/runs/{run['id']}/steps/{hold['step']['n']}/reject")
    out = (await call).json()["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert (await api(served, "GET", "/api/policy/responses")).json() == before


async def test_each_call_records_the_agent_its_model_and_its_subagent(served):
    """The act record: the model from SessionStart, then from a model switch; a subagent's
    call says which one made it."""
    run = await new_run(served)
    key = run["key"]
    model = "claude-opus-5-5"
    await hook(
        served, key, session_event("SessionStart", source="startup", model=model)
    )
    read = {"file_path": "README.md"}
    await hook(served, key, event("PreToolUse", "Read", "t1", tool_input=read))
    switch = session_event(
        "PostModelSwitch",
        from_model=model,
        to_model="claude-sonnet-5-5",
        source="command",
    )
    assert (await hook(served, key, switch)).json() == {}
    sub = {"agent_id": "a7", "agent_type": "Explore"}
    await hook(served, key, event("PreToolUse", "Read", "t2", tool_input=read, **sub))
    steps = (await run_of(served, run))["steps"]
    assert [(s["surface"], s["agent"]) for s in steps] == [
        ("hook", {"client": "claude-code", "client_version": None, "model": model,
                  "sub_agent": None, "sub_agent_type": None}),
        ("hook", {"client": "claude-code", "client_version": None,
                  "model": "claude-sonnet-5-5", "sub_agent": "a7",
                  "sub_agent_type": "Explore"}),
    ]  # fmt: skip


async def test_each_call_says_who_asked_for_it(served):
    """A value the user typed asked for the call; the agent's own choice is the agent's."""
    run = await new_run(served)
    key = run["key"]
    prompt = session_event("UserPromptSubmit", prompt="Open releases/2026-10-12.md")
    await hook(served, key, prompt)
    opened = {"file_path": "releases/2026-10-12.md"}
    await hook(served, key, event("PreToolUse", "Read", "t1", tool_input=opened))
    await hook(
        served, key, event("PreToolUse", "Read", "t2", tool_input={"file_path": "a"})
    )
    steps = (await run_of(served, run))["steps"]
    assert [s["asked_by"] for s in steps] == [["user"], ["agent"]]


async def test_an_event_cressey_does_not_follow_is_answered_with_nothing(served):
    run = await new_run(served)
    out = await hook(served, run["key"], session_event("SubagentStart", agent_id="a7"))
    assert (out.status_code, out.json()) == (200, {})
