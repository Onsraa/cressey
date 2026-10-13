"""What an ended run keeps: what was decided, not what its calls returned, and nothing of a
call or a message its session's end cut short."""

import asyncio
import threading
import time
from collections.abc import Callable, Mapping

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cressey.app import create_app
from cressey.engine.agent_text import ENDED
from cressey.judge import Judge
from cressey.settings import Settings
from cressey.testing import ADMIN, ADMIN_AUTH, QuietJudge, fake_guide, no_to_all

BIG = "row\n" * 25_000  # 100 KB a call returned


def _app(judge: Judge) -> FastAPI:
    s = Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        admin_token=ADMIN,
        hold_timeout=0.3,
    )
    return create_app(s, make_guide=fake_guide, judge=judge)


class Session:
    """A Claude Code session on a new run, through the hook."""

    def __init__(self, c: TestClient) -> None:
        self.c = c
        body = {"task": "Reset the staging database"}
        created = c.post("/api/runs", json=body, headers=ADMIN_AUTH).json()
        self.id, self.auth = (
            created["id"],
            {"Authorization": f"Bearer {created['key']}"},
        )

    def send(self, kind: str, **extra) -> None:
        body = {"hook_event_name": kind, "session_id": "s1", "cwd": "/work", **extra}
        assert self.c.post("/hook/claude", json=body, headers=self.auth).is_success

    def read(self, call: str, returned: str) -> None:
        tool = {
            "tool_name": "Read",
            "tool_use_id": call,
            "tool_input": {"file_path": f"{call}.md"},
        }
        self.send("PreToolUse", **tool)
        self.send("PostToolUse", **tool, tool_response=returned)


def until(done: Callable[[], bool]) -> None:
    for _ in range(300):
        if done():
            return
        time.sleep(0.01)
    raise AssertionError("not settled")


class GatedJudge:
    """Answers no to everything once `open` is set: until then, every read is in flight."""

    def __init__(self) -> None:
        self.open = threading.Event()

    async def answers(self, state: dict, questions: Mapping) -> dict:
        await asyncio.to_thread(self.open.wait)
        return no_to_all(questions)


class ToolKindGate:
    """Answers no to everything at once, but the kind of a tool no catalog lists only once
    `open` is set: until then, a call to such a tool is still being decided. `kind` is the
    answer then given (by default none, so the floor holds the call)."""

    def __init__(self, kind: dict[str, float] | None = None) -> None:
        self.asked, self.open = threading.Event(), threading.Event()
        self.kind = kind

    async def answers(self, state: dict, questions: Mapping) -> dict:
        answered = no_to_all(questions)
        if "kind" in questions:
            self.asked.set()
            await asyncio.to_thread(self.open.wait)
            if self.kind is not None:
                answered["kind"] = self.kind
        return answered


# An MCP tool no catalog lists, which Jev labels a read once asked.
SEARCH = {
    "tool_name": "mcp__docs__search",
    "tool_use_id": "q1",
    "tool_input": {"query": "staging reset"},
}


def test_a_call_decided_over_the_end_keeps_the_trail_of_what_the_run_read():
    """A call that came in before the run ended is decided on what the run had read: the
    end drops nothing the decision still needs, such as who asked for the call."""
    judge = ToolKindGate()
    app = _app(judge)
    iban = "DE89370400440532013000"
    with TestClient(app) as c:
        s = Session(c)
        s.read("t1", f"New bank details: {iban}")
        pay = {
            "tool_name": "mcp__bank__pay",
            "tool_use_id": "p1",
            "tool_input": {"iban": iban, "amount": "100"},
        }
        deciding = threading.Thread(target=s.send, args=("PreToolUse",), kwargs=pay)
        deciding.start()
        until(judge.asked.is_set)
        report = {"text": "Paid."}
        assert c.post(
            f"/api/runs/{s.id}/report", json=report, headers=s.auth
        ).is_success
        time.sleep(0.2)
        [read] = app.state.runs.get(s.id).steps
        kept = read.result
        judge.open.set()
        deciding.join()
        [_, paid] = app.state.runs.get(s.id).steps
        until(lambda: read.result == "")  # once decided, the end drops it
    assert kept == f"New bank details: {iban}"
    assert paid.asked_by == ["content"]


def test_a_session_end_forgets_the_calls_left_running():
    app = _app(QuietJudge())
    with TestClient(app) as c:
        s = Session(c)
        call = {"tool_name": "Read", "tool_use_id": "t1"}
        s.send("PreToolUse", **call, tool_input={"file_path": "a.md"})
        s.send("SessionEnd")  # killed mid-call: its PostToolUse never comes
        [step] = app.state.runs.get(s.id).steps
    assert app.state.hook_calls == {} and not step.running


def test_a_session_end_forgets_a_call_still_being_decided():
    """Killed while Cressey decides a call: once let through, the call isn't kept waiting
    for a result that never comes."""
    judge = ToolKindGate(kind={"read": 1.0})
    app = _app(judge)
    with TestClient(app) as c:
        s = Session(c)
        deciding = threading.Thread(target=s.send, args=("PreToolUse",), kwargs=SEARCH)
        deciding.start()
        until(judge.asked.is_set)
        s.send("SessionEnd")
        judge.open.set()
        deciding.join()
        [step] = app.state.runs.get(s.id).steps
    assert step.status == "allowed"
    assert app.state.hook_calls == {} and not step.running


def test_a_report_keeps_a_call_decided_over_it_until_its_result_comes():
    """A report ends the run, not the session: Claude Code still runs the call and sends
    what it returned, which is recorded, then dropped with the rest."""
    judge = ToolKindGate(kind={"read": 1.0})
    app = _app(judge)
    with TestClient(app) as c:
        s = Session(c)
        deciding = threading.Thread(target=s.send, args=("PreToolUse",), kwargs=SEARCH)
        deciding.start()
        until(judge.asked.is_set)
        report = {"text": "Done."}
        assert c.post(
            f"/api/runs/{s.id}/report", json=report, headers=s.auth
        ).is_success
        judge.open.set()
        deciding.join()
        s.send("PostToolUse", **SEARCH, tool_response=BIG)
        [step] = app.state.runs.get(s.id).steps
        until(lambda: step.result == "")
    assert step.scan_ms is not None  # what it returned was read
    assert app.state.hook_calls == {} and not step.running


def test_a_session_end_drops_what_the_runs_calls_returned():
    app = _app(QuietJudge())
    with TestClient(app) as c:
        s = Session(c)
        s.read("t1", BIG)
        [step] = app.state.runs.get(s.id).steps
        assert step.result == BIG
        s.send("SessionEnd")
        until(lambda: step.result == "")


def test_a_report_ends_the_run_and_drops_what_its_calls_returned():
    app = _app(QuietJudge())
    with TestClient(app) as c:
        s = Session(c)
        s.read("t1", BIG)
        [step] = app.state.runs.get(s.id).steps
        report = {"text": "The staging database is reset."}
        assert c.post(
            f"/api/runs/{s.id}/report", json=report, headers=s.auth
        ).is_success
        until(lambda: step.result == "")


def test_what_a_call_returned_stays_while_a_read_of_it_is_in_flight():
    judge = GatedJudge()
    app = _app(judge)
    with TestClient(app) as c:
        s = Session(c)
        s.read("t1", BIG)  # the ledger's label of it waits for the judge
        [step] = app.state.runs.get(s.id).steps
        s.send("SessionEnd")
        time.sleep(0.2)
        kept = step.result
        judge.open.set()
        until(lambda: step.result == "")
    assert kept == BIG


def test_a_session_resumed_before_its_reads_end_keeps_what_its_calls_returned():
    judge = GatedJudge()
    app = _app(judge)
    with TestClient(app) as c:
        s = Session(c)
        s.read("t1", BIG)
        [step] = app.state.runs.get(s.id).steps
        s.send("SessionEnd")
        s.send("SessionStart", source="resume")  # claude --resume
        judge.open.set()
        until(lambda: step.labels is not None)
        time.sleep(0.1)
    assert step.result == BIG


def test_a_session_end_drops_the_arguments_a_call_carried_too():
    """Only an incident opening reads them; the record keeps their redacted form."""
    app = _app(QuietJudge())
    with TestClient(app) as c:
        s = Session(c)
        wrote = {"file_path": "notes.md", "content": BIG}
        call = {"tool_name": "Write", "tool_use_id": "w1", "tool_input": wrote}
        s.send("PreToolUse", **call)
        s.send("PostToolUse", **call, tool_response="written")
        [step] = app.state.runs.get(s.id).steps
        assert step.raw_args == wrote
        s.send("SessionEnd")
        until(lambda: step.raw_args == {})
    assert "notes.md" in step.args  # the shown, redacted form stays


def test_an_ended_run_refuses_calls_until_a_prompt_reopens_it():
    """An agent that ends its own run (its report) can't go on acting with the trail of
    what it read dropped; the user's next prompt starts a new turn."""
    app = _app(QuietJudge())
    with TestClient(app) as c:
        s = Session(c)
        s.read("t1", "the ops token is in .env")
        report = {"text": "Done."}
        assert c.post(
            f"/api/runs/{s.id}/report", json=report, headers=s.auth
        ).is_success
        call = {"tool_name": "Read", "tool_input": {"file_path": "b.md"}}
        body = {"hook_event_name": "PreToolUse", "session_id": "s1", "cwd": "/w"}
        after = c.post(
            "/hook/claude", json={**body, **call, "tool_use_id": "t2"}, headers=s.auth
        ).json()
        s.send("UserPromptSubmit", prompt="carry on")
        again = c.post(
            "/hook/claude", json={**body, **call, "tool_use_id": "t3"}, headers=s.auth
        ).json()
    denied = after["hookSpecificOutput"]
    assert (denied["permissionDecision"], denied["permissionDecisionReason"]) == (
        "deny",
        ENDED,
    )
    assert again == {}


def test_a_result_that_comes_after_the_end_is_dropped_too():
    """A call held over the end, approved later: what it returned goes as well."""
    app = _app(QuietJudge())
    with TestClient(app) as c:
        s = Session(c)
        rm = {
            "tool_name": "Bash",
            "tool_use_id": "b1",
            "tool_input": {"command": "rm -rf build"},
        }
        held = threading.Thread(target=s.send, args=("PreToolUse",), kwargs=rm)
        held.start()
        until(lambda: c.get("/api/holds", headers=ADMIN_AUTH).json() != [])
        s.send("SessionEnd")
        assert c.post(
            f"/api/runs/{s.id}/steps/1/approve", headers=ADMIN_AUTH
        ).is_success
        held.join()
        s.send("PostToolUse", **rm, tool_response=BIG)
        [step] = app.state.runs.get(s.id).steps
        until(lambda: step.result == "")
