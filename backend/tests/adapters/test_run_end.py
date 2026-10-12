"""What an ended run keeps: what was decided, not what its calls returned, and nothing of a
call or a message its session's end cut short."""

import asyncio
import threading
import time
from collections.abc import Callable, Mapping

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cressey.app import create_app
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


def test_a_session_end_forgets_the_calls_left_running():
    app = _app(QuietJudge())
    with TestClient(app) as c:
        s = Session(c)
        call = {"tool_name": "Read", "tool_use_id": "t1"}
        s.send("PreToolUse", **call, tool_input={"file_path": "a.md"})
        s.send("SessionEnd")  # killed mid-call: its PostToolUse never comes
        [step] = app.state.runs.get(s.id).steps
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
