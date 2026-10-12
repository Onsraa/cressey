"""A restart keeps the runs' keys, their step numbers and an event log checked against its
anchor: a new Cressey reading the same folder carries on."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cressey.app import create_app
from cressey.core.eventlog import EventLog
from cressey.core.runs import Runs
from cressey.domain.runs import RunIn
from cressey.settings import Settings
from tests.server import ADMIN_AUTH

pytestmark = pytest.mark.anyio
TASK = "Fix the failing test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _cressey(folder: Path) -> Runs:
    """What a start reads: the log, its anchor and the runs' keys, as create_app opens them."""
    log = EventLog(folder / "events.jsonl", folder / "anchor.json")
    return Runs(log, folder / "runs.jsonl")


async def test_a_restart_keeps_the_key_the_steps_and_expires_an_open_hold(tmp_path):
    runs = _cressey(tmp_path)
    created = runs.create(RunIn(task=TASK))
    run = runs.get(created.id)
    assert run is not None
    read = runs.add_step(run, "Read", {}, '{"file_path": "a"}', "read", None)
    runs.mark(run, read, "alerted")
    rm = runs.add_step(run, "Bash", {}, '{"command": "rm -r x"}', "destructive", "rm")
    holding = asyncio.create_task(runs.hold(run, rm, timeout=60, stop_after=3))
    await asyncio.sleep(0)  # the hold is logged; Cressey stops before anyone decides

    restarted = _cressey(tmp_path)
    holding.cancel()
    again = restarted.by_key(created.key)
    assert again is not None and again.id == created.id
    assert [(s.n, s.tool, s.status) for s in again.steps] == [
        (1, "Read", "alerted"),
        (2, "Bash", "expired"),
    ]
    expired = restarted.log.events[-1]
    assert expired.data == {
        "run": run.id,
        "n": 2,
        "status": "expired",
        "after": "restart",
    }
    assert restarted.add_step(again, "Read", {}, "{}", "read", None).n == 3
    assert restarted.log.intact


def test_a_later_session_keeps_its_own_run_after_a_restart(tmp_path):
    runs = _cressey(tmp_path)
    created = runs.create(RunIn(task=TASK))
    first = runs.get(created.id)
    assert first is not None
    assert runs.for_session(first, "s1") is first
    later = runs.for_session(first, "s2")

    restarted = _cressey(tmp_path)
    again = restarted.by_key(created.key)
    assert again is not None
    assert restarted.for_session(again, "s1") is again
    assert restarted.for_session(again, "s2").id == later.id


def _append(folder: Path, n: int) -> None:
    log = EventLog(folder / "events.jsonl", folder / "anchor.json")
    for i in range(n):
        log.append("call", {"i": i})


def test_an_untouched_log_is_intact_after_a_restart(tmp_path):
    _append(tmp_path, 4)
    assert EventLog(tmp_path / "events.jsonl", tmp_path / "anchor.json").intact


def test_a_log_cut_short_is_caught_by_its_anchor(tmp_path):
    _append(tmp_path, 4)
    events = tmp_path / "events.jsonl"
    events.write_text("".join(events.read_text().splitlines(keepends=True)[:-1]))
    assert not EventLog(events, tmp_path / "anchor.json").intact


def test_a_log_whose_anchor_is_gone_cant_be_vouched_for(tmp_path):
    _append(tmp_path, 4)
    (tmp_path / "anchor.json").unlink()
    assert not EventLog(tmp_path / "events.jsonl", tmp_path / "anchor.json").intact


def test_a_first_start_has_nothing_to_check(tmp_path):
    assert EventLog(tmp_path / "events.jsonl", tmp_path / "anchor.json").intact


def _app(state: Path) -> TestClient:
    s = Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        state_dir=state,
    )
    return TestClient(create_app(s))


def test_the_dashboard_sees_a_tampered_log_and_old_keys_keep_working(tmp_path):
    state = tmp_path / "state"
    c = _app(state)
    run = c.post("/api/runs", json={"task": TASK}, headers=ADMIN_AUTH).json()
    assert c.get("/api/status", headers=ADMIN_AUTH).json()["log"]["intact"]

    after = _app(state)
    as_agent = {"Authorization": f"Bearer {run['key']}"}
    start = {"hook_event_name": "SessionStart", "session_id": "s1", "cwd": "/w"}
    assert after.post("/hook/claude", json=start, headers=as_agent).status_code == 200
    assert after.get("/api/status", headers=ADMIN_AUTH).json()["log"]["intact"]

    events = state / "events.jsonl"
    events.write_text(events.read_text().splitlines(keepends=True)[0])
    tampered = _app(state).get("/api/status", headers=ADMIN_AUTH).json()
    assert not tampered["log"]["intact"]
