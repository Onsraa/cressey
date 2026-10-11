import asyncio

import pytest
from pydantic import JsonValue

from cressey.core.eventlog import EventLog
from cressey.core.models import (
    Leg,
    Legs,
    Message,
    Run,
    RunIn,
    Shadow,
    Step,
    TextIn,
    Thresholds,
)
from cressey.core.runs import Runs

ON = Leg(score=1, confirmed=True, facts=[])
OFF = Leg(score=0, confirmed=False, facts=[])


def test_acting_on_pressure_is_logged_once_each():
    runs = Runs(EventLog())
    run = runs.get(runs.create(RunIn(task="fais passer les tests")).id)
    assert run is not None
    pressure = Legs(pressure=ON, opportunity=OFF, rationalization=OFF)
    with_key = Legs(pressure=ON, opportunity=ON, rationalization=OFF)
    for n, legs in enumerate([pressure, with_key, with_key], start=1):
        args: dict[str, JsonValue] = {"path": f"f{n}.md"}
        step = runs.add_step(run, "read_file", args, str(args), "read", None)
        runs.act_on_pressure(run, step, legs)
    acted = [
        (e.kind, e.data["n"])
        for e in runs.log.events
        if e.kind in ("way_out", "read_only")
    ]
    assert acted == [("way_out", 1), ("read_only", 2)]
    assert (run.way_out_step, run.read_only_step) == (1, 2)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _held_pair() -> tuple[Runs, Run, list[Step]]:
    """A run with two destructive calls, both about to wait for a human."""
    runs = Runs(EventLog())
    run = runs.get(runs.create(RunIn(task="nettoyer la base")).id)
    assert run is not None
    calls = [
        runs.add_step(run, "run_sql", {"q": q}, q, "destructive", "hors mandat")
        for q in ("DELETE FROM a", "DELETE FROM b")
    ]
    return runs, run, calls


@pytest.mark.anyio
async def test_approving_one_of_two_holds_keeps_the_key_until_the_other_is_decided():
    runs, run, calls = _held_pair()
    waits = [asyncio.create_task(runs.hold(run, c, 5)) for c in calls]
    await asyncio.sleep(0)
    assert runs.decide(run.id, 1, True)
    assert await waits[0]  # the approved call itself may run
    assert run.revoked  # the other one still waits for a human
    assert runs.decide(run.id, 2, True)
    assert await waits[1] and not run.revoked


@pytest.mark.anyio
async def test_a_rejection_keeps_the_key_suspended_after_another_hold_is_approved():
    runs, run, calls = _held_pair()
    waits = [asyncio.create_task(runs.hold(run, c, 5)) for c in calls]
    await asyncio.sleep(0)
    assert runs.decide(run.id, 1, False)
    assert not await waits[0]
    assert runs.decide(run.id, 2, True)
    assert await waits[1] and run.revoked


@pytest.mark.anyio
async def test_a_prompt_unlocks_the_key_but_not_while_a_call_is_held():
    runs, run, calls = _held_pair()
    first = asyncio.create_task(runs.hold(run, calls[0], 5))
    await asyncio.sleep(0)
    runs.prompt(run, "wait, what are you doing?")  # typed while the call is held
    assert run.revoked
    runs.decide(run.id, 1, False)
    assert not await first and run.revoked
    runs.prompt(run, "ok, leave prod alone")
    assert not run.revoked
    # The rejection before the prompt no longer counts: approving a later hold leaves
    # the key open.
    later = runs.add_step(run, "run_sql", {"q": "x"}, "x", "destructive", "hors mandat")
    second = asyncio.create_task(runs.hold(run, later, 5))
    await asyncio.sleep(0)
    runs.decide(run.id, later.n, True)
    assert await second and not run.revoked


def test_a_prompt_closes_a_message_left_streaming():
    """Claude Code sends nothing on Esc: a message cut short stays open until the next
    prompt, which closes it."""
    runs = Runs(EventLog())
    run = runs.get(runs.create(RunIn(task="nettoyer la base")).id)
    assert run is not None
    runs.stream(run, "m1", "I'll delete the", False)
    runs.prompt(run, "stop")
    assert [m.streaming for m in run.messages] == [False, False]


def test_a_run_serves_its_case_and_messages_their_source():
    runs = Runs(EventLog())
    run = runs.get(runs.create(RunIn(task="reset staging")).id)
    assert run is not None
    assert run.model_dump()["case"] == {
        "events": [],
        "threads": [],
        "approved": [],
        "notes": [],
    }
    assert Message(after=0, text="hi").source == "narration"
    assert TextIn(text="x", source="reasoning").source == "reasoning"
    assert Thresholds().thoughts["R"] == 0.2 and Thresholds().thoughts["about"] == 0.5


def test_the_log_keeps_who_said_it_not_the_flags():
    """A message is logged with its role, never with the flags a model adds later."""
    runs = Runs(EventLog())
    run = runs.get(runs.create(RunIn(task="nettoyer la base")).id)
    assert run is not None
    runs.say(run, "I'll look first.")
    runs.stream(run, "m1", "Then I'll clean.", True)
    runs.prompt(run, "stop")
    logged = [e.data for e in runs.log.events if e.kind == "message"]
    assert [sorted(d) for d in logged] == [
        ["after", "role", "run", "streaming", "text"]
    ] * 3
    assert [d["role"] for d in logged] == ["agent", "agent", "user"]


def test_a_shadow_is_stored_on_its_step_and_logged():
    runs = Runs(EventLog())
    run = runs.get(runs.create(RunIn(task="fais passer les tests")).id)
    assert run is not None
    step = runs.add_step(run, "Bash", {}, "{}", "write", None)
    shadow = Shadow(decision="hold", why=["a link"], uses=["svc:9"], words_read=False)
    runs.set_shadow(run, step, shadow)
    assert step.shadow == shadow
    [event] = [e for e in runs.log.events if e.kind == "shadow"]
    assert event.data == {
        "run": run.id,
        "n": 1,
        "decision": "hold",
        "uses": ["svc:9"],
        "words_read": False,
    }
