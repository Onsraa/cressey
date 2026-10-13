"""A write too long to read before it runs still runs (no hold for a technical reason, the
user's 10-10 rule) and is read afterwards: the floor's labels as well as the triangle. One
they flag, or one no model answers, alerts with its incident open: it never runs unjudged
in silence. A file edit, whose path code checked, is the exception, as before it runs."""

import asyncio
import json
from collections.abc import Mapping

import pytest

from cressey.engine import reading
from cressey.judge import Judge
from cressey.testing import DownJudge, api, no_to_all, serving, traced_incidents

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


async def test_the_incident_of_a_write_read_afterwards_hides_what_its_own_scan_finds(
    tmp_path,
):
    """Its sources hide what the arguments hide: a value the scan of the whole call finds
    (`api_key: ...`), read earlier in plain text, which no scan of that result flagged."""
    unseen = "unseen-value-4242"
    write = f"{PADDED}api_key: {unseen} (rotated)\n"
    calls = [
        ("c1", "cat ops.txt", f"rotation value {unseen} from ops"),
        ("c2", write, "done"),
    ]
    with serving(tmp_path, hold_timeout=10, judge=Irreversible()) as base:
        body = {"task": "Tidy the infrastructure"}
        run = (await api(base, "POST", "/api/runs", json=body)).json()
        auth = {"Authorization": f"Bearer {run['key']}"}
        for call, command, result in calls:
            event = {
                "session_id": "s1",
                "tool_name": "Bash",
                "tool_use_id": call,
                "tool_input": {"command": command},
            }
            for kind, extra in (
                ("PreToolUse", {}),
                ("PostToolUse", {"tool_response": result}),
            ):
                sent = {**event, "hook_event_name": kind, **extra}
                await api(base, "POST", "/hook/claude", json=sent, headers=auth)
        for _ in range(500):
            page = (await api(base, "GET", f"/api/runs/{run['id']}")).json()
            if page["steps"][-1]["status"] == "alerted":  # read afterwards, flagged
                break
            await asyncio.sleep(0.02)
        [incident] = await traced_incidents(base)
    assert [s["step"] for s in incident["sources"]] == [1]  # traced to the read
    assert unseen not in json.dumps(incident)


async def late_then_next(tmp_path, responses: dict) -> tuple[dict, dict]:
    """A long write the floor flags once it ran, under these responses, then the next call:
    the run once that write was read, and Cressey's answer to the next call."""
    with serving(tmp_path, hold_timeout=10, judge=Irreversible()) as base:
        now = (await api(base, "GET", "/api/policy/responses")).json()
        changed = {**now, **responses}
        assert (
            await api(base, "PUT", "/api/policy/responses", json=changed)
        ).is_success
        body = {"task": "Tidy the infrastructure"}
        run = (await api(base, "POST", "/api/runs", json=body)).json()
        auth = {"Authorization": f"Bearer {run['key']}"}

        async def send(kind: str, call: str, command: str, **extra) -> dict:
            event = {
                "hook_event_name": kind,
                "session_id": "s1",
                "tool_name": "Bash",
                "tool_use_id": call,
                "tool_input": {"command": command},
                **extra,
            }
            sent = await api(base, "POST", "/hook/claude", json=event, headers=auth)
            return sent.json()

        assert await send("PreToolUse", "c1", PADDED) == {}  # it runs
        await send("PostToolUse", "c1", PADDED, tool_response="done")
        for _ in range(250):
            page = (await api(base, "GET", f"/api/runs/{run['id']}")).json()
            if page["steps"][0]["status"] == "alerted":  # read afterwards, flagged
                break
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.1)
        page = (await api(base, "GET", f"/api/runs/{run['id']}")).json()
        after = await send("PreToolUse", "c2", "ls")
    return page, after


async def test_under_a_stop_response_a_write_flagged_once_it_ran_suspends_the_key(
    tmp_path,
):
    """What already ran can't be held, but the policy's stop still applies: the rest of the
    run is refused until a human unlocks it (the user, 10-13)."""
    page, after = await late_then_next(tmp_path, {"irreversible": "stop"})
    assert page["steps"][0]["status"] == "alerted"
    assert page["revoked"] and page["stop_step"] == 1
    assert after["hookSpecificOutput"]["permissionDecision"] == "deny"


async def test_under_review_a_write_flagged_once_it_ran_leaves_the_key_usable(tmp_path):
    """Review can't hold what already ran: the incident asks a human, the run goes on."""
    page, after = await late_then_next(tmp_path, {})
    assert page["steps"][0]["status"] == "alerted"
    assert not page["revoked"] and page.get("stop_step") is None
    assert after == {}
