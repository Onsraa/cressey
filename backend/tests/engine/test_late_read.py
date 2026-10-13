"""A write too long to read before it runs still runs (no hold for a technical reason, the
user's 10-10 rule) and is read afterwards: the floor's labels as well as the triangle. One
they flag, or one no model answers, alerts with its incident open: it never runs unjudged
in silence. A file edit, whose path code checked, is the exception, as before it runs."""

import asyncio
from collections.abc import Mapping

import pytest

from cressey.engine import reading
from cressey.judge import Judge
from cressey.testing import DownJudge, api, no_to_all, serving

pytestmark = pytest.mark.anyio
PADDED = "terraform destroy -auto-approve\n" + "# keep the plan for later\n" * 600


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def one_part(monkeypatch):
    """Anything longer than one part is too long to read before it runs."""
    monkeypatch.setattr(reading, "PARTS_BEFORE", 1)


class Irreversible:
    """The floor finds every write irreversible; every other question gets no."""

    async def answers(self, state: dict, questions: Mapping) -> dict:
        got = no_to_all(questions)
        if "irreversible" in questions:
            got["irreversible"] = 0.9
        return got


async def ran_long(tmp_path, judge: Judge, tool: str, args: dict) -> tuple[dict, list]:
    """The call through the hook, let through at once; its step once read afterwards, and
    the incidents."""
    with serving(tmp_path, hold_timeout=10, judge=judge) as base:
        body = {"task": "Tidy the infrastructure"}
        run = (await api(base, "POST", "/api/runs", json=body)).json()
        auth = {"Authorization": f"Bearer {run['key']}"}
        call = {"tool_name": tool, "tool_use_id": "c1", "tool_input": args}

        async def send(kind: str, **extra) -> dict:
            event = {"hook_event_name": kind, "session_id": "s1", **call, **extra}
            sent = await api(base, "POST", "/hook/claude", json=event, headers=auth)
            return sent.json()

        assert await send("PreToolUse") == {}  # it runs
        await send("PostToolUse", tool_response="done")
        for _ in range(500):
            page = (await api(base, "GET", f"/api/runs/{run['id']}")).json()
            [step] = page["steps"]
            if step["legs"] is not None:  # read afterwards
                break
            await asyncio.sleep(0.02)
        incidents = (await api(base, "GET", "/api/incidents")).json()
    return step, incidents


def checks(step: dict) -> list[tuple[str, bool]]:
    return [(r["check"], r["afterwards"]) for r in step["reasons"]]


async def test_with_no_model_answering_a_long_write_alerts_once_it_ran(tmp_path):
    step, incidents = await ran_long(tmp_path, DownJudge(), "Bash", {"command": PADDED})
    assert (step["status"], checks(step)) == ("alerted", [("no_answer", True)])
    assert len(incidents) == 1


async def test_a_long_write_the_floor_flags_alerts_once_it_ran(tmp_path):
    step, incidents = await ran_long(
        tmp_path, Irreversible(), "Bash", {"command": PADDED}
    )
    assert (step["status"], checks(step)) == ("alerted", [("irreversible", True)])
    assert len(incidents) == 1


async def test_a_long_file_edit_runs_quiet(tmp_path):
    edit = {"file_path": "notes.md", "content": PADDED}
    step, incidents = await ran_long(tmp_path, DownJudge(), "Write", edit)
    assert (step["status"], checks(step), incidents) == ("allowed", [], [])
