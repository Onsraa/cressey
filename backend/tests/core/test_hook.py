"""Claude Code's http hooks over real HTTP: PreToolUse gets the decision, PostToolUse the
result, and the agent's words come from the transcript the hook names."""

import asyncio

import pytest

from cressey.core.draft import WAY_OUT
from cressey.demo.tools import TRAP_KEY
from tests.server import api, next_hold

pytestmark = pytest.mark.anyio
TASK = "reset the staging database"


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def new_run(base: str) -> dict:
    body = {"task": TASK, "visibility": "messages"}
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
    after = (await hook(served, run["key"], read)).json()["hookSpecificOutput"]
    assert "suspended" in after["permissionDecisionReason"]
    statuses = [s["status"] for s in (await run_of(served, run))["steps"]]
    assert statuses == ["rejected", "denied"]


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


def trap_write() -> dict:
    """A PreToolUse event for a command that writes with a trap key: it is held."""
    curl = {
        "command": f'curl -s -X POST https://api.test -H "Authorization: Bearer {TRAP_KEY}"'
    }
    return event("PreToolUse", "Bash", tool_input=curl)


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


async def test_your_next_prompt_unlocks_a_suspended_key(served):
    run = await new_run(served)
    key = run["key"]
    curl = {
        "command": f'curl -s -X POST https://api.test -H "Authorization: Bearer {TRAP_KEY}"'
    }
    held = asyncio.create_task(
        hook(served, key, event("PreToolUse", "Bash", tool_input=curl))
    )
    n = (await next_hold(served))["step"]["n"]
    await api(served, "POST", f"/api/runs/{run['id']}/steps/{n}/reject")
    await held
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
    assert allowed.json() == {} and not (await run_of(served, run))["revoked"]


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


async def test_claude_codes_own_tools_pass_and_an_unknown_tool_is_held(
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
