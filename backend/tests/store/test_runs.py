import asyncio

import pytest
from pydantic import JsonValue

from cressey.domain.policy import Thresholds
from cressey.domain.reasons import Reason
from cressey.domain.runs import Leg, Legs, Message, Run, RunIn, Shadow, Step, TextIn
from cressey.engine.decide import act_on_pressure
from cressey.store.eventlog import EventLog
from cressey.store.runs import Runs
from tests.helpers import act

ON = Leg(score=1, confirmed=True, facts=[])
OFF = Leg(score=0, confirmed=False, facts=[])
HELD = [Reason(check="destructive_sql", target="a")]


def test_acting_on_pressure_is_logged_once_each():
    runs = Runs(EventLog())
    run = runs.get(runs.create(RunIn(task="fais passer les tests")).id)
    assert run is not None
    pressure = Legs(pressure=ON, opportunity=OFF, rationalization=OFF)
    with_key = Legs(pressure=ON, opportunity=ON, rationalization=OFF)
    for n, legs in enumerate([pressure, with_key, with_key], start=1):
        args: dict[str, JsonValue] = {"path": f"f{n}.md"}
        step = runs.add_step(
            run, act("read_file", args), str(args), "read", [], ["agent"]
        )
        act_on_pressure(runs, run, step, legs)
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
        runs.add_step(run, act("run_sql", {"q": q}), q, "destructive", HELD, ["agent"])
        for q in ("DELETE FROM a", "DELETE FROM b")
    ]
    return runs, run, calls


async def _rejected(runs: Runs, run: Run, step: Step, stop_after: int = 3) -> None:
    """A call held, then rejected by a human."""
    wait = asyncio.create_task(runs.hold(run, step, 5, stop_after))
    await asyncio.sleep(0)
    assert runs.decide(run.id, step.n, False)
    assert not await wait


def _call(runs: Runs, run: Run) -> Step:
    return runs.add_step(
        run, act("run_sql", {"q": "x"}), "x", "destructive", HELD, ["agent"]
    )


@pytest.mark.anyio
async def test_approving_one_of_two_holds_keeps_the_key_until_the_other_is_decided():
    runs, run, calls = _held_pair()
    waits = [asyncio.create_task(runs.hold(run, c, 5, 3)) for c in calls]
    await asyncio.sleep(0)
    assert runs.decide(run.id, 1, True)
    assert await waits[0]  # the approved call itself may run
    assert run.revoked  # the other one still waits for a human
    assert runs.decide(run.id, 2, True)
    assert await waits[1] and not run.revoked


@pytest.mark.anyio
async def test_a_rejection_alone_leaves_the_key_usable():
    runs, run, calls = _held_pair()
    wait = asyncio.create_task(runs.hold(run, calls[0], 5, 3))
    await asyncio.sleep(0)
    assert run.revoked  # while the call is held
    assert runs.decide(run.id, 1, False)
    assert not await wait
    assert (run.revoked, run.refused, run.stopped) == (False, 1, False)


@pytest.mark.anyio
async def test_an_expiry_counts_as_a_refusal_and_an_approval_does_not():
    runs, run, calls = _held_pair()
    assert not await runs.hold(run, calls[0], 0.01, 3)  # nobody decides in time
    assert (calls[0].status, run.refused) == ("expired", 1)
    wait = asyncio.create_task(runs.hold(run, calls[1], 5, 3))
    await asyncio.sleep(0)
    assert runs.decide(run.id, 2, True)
    assert await wait and (run.revoked, run.refused) == (False, 1)


@pytest.mark.anyio
async def test_the_third_rejection_stops_the_run_and_unlock_undoes_it():
    runs, run, calls = _held_pair()
    for step in calls:
        await _rejected(runs, run, step)
        assert not run.stopped and not run.revoked
    await _rejected(runs, run, _call(runs, run))
    assert (run.refused, run.stopped, run.revoked) == (3, True, True)
    runs.unlock(run)
    assert (run.refused, run.stopped, run.revoked) == (0, False, False)
    unlocked = runs.log.events[-1]
    assert (unlocked.kind, unlocked.data) == (
        "unlocked",
        {"run": run.id, "key": "cleared"},
    )


async def _cancelled(runs: Runs, run: Run, step: Step, stop_after: int = 3) -> None:
    """A call held, then abandoned: its caller is cancelled."""
    wait = asyncio.create_task(runs.hold(run, step, 5, stop_after))
    await asyncio.sleep(0)
    wait.cancel()
    with pytest.raises(asyncio.CancelledError):
        await wait


@pytest.mark.anyio
async def test_a_cancelled_hold_counts_as_expired_and_frees_the_key():
    runs, run, calls = _held_pair()
    await _cancelled(runs, run, calls[0])
    assert calls[0].status == "expired"
    assert (run.refused, run.stopped, run.revoked) == (1, False, False)


@pytest.mark.anyio
async def test_a_cancelled_third_hold_stops_the_run():
    runs, run, calls = _held_pair()
    await _rejected(runs, run, calls[0])
    await _rejected(runs, run, calls[1])
    await _cancelled(runs, run, _call(runs, run))
    assert (run.refused, run.stopped, run.revoked) == (3, True, True)


@pytest.mark.anyio
async def test_unlock_leaves_the_key_suspended_while_a_call_is_held():
    runs, run, calls = _held_pair()
    wait = asyncio.create_task(runs.hold(run, calls[0], 5, 3))
    await asyncio.sleep(0)
    runs.unlock(run)
    assert run.revoked
    unlocked = runs.log.events[-1]  # a human's Unlock is logged either way
    assert (unlocked.kind, unlocked.data) == (
        "unlocked",
        {"run": run.id, "key": "held"},
    )
    runs.decide(run.id, 1, True)
    assert await wait and not run.revoked


@pytest.mark.anyio
async def test_two_parallel_holds_both_count_and_the_key_waits_for_both():
    runs, run, calls = _held_pair()
    waits = [asyncio.create_task(runs.hold(run, c, 5, 3)) for c in calls]
    await asyncio.sleep(0)
    assert runs.decide(run.id, 1, False)
    assert not await waits[0]
    assert run.revoked and run.refused == 1  # the second still waits for a human
    assert runs.decide(run.id, 2, False)
    assert not await waits[1]
    assert (run.refused, run.revoked) == (2, False)


@pytest.mark.anyio
async def test_a_prompt_unlocks_the_key_but_not_while_a_call_is_held():
    runs, run, calls = _held_pair()
    first = asyncio.create_task(runs.hold(run, calls[0], 5, 1))
    await asyncio.sleep(0)
    runs.prompt(run, "wait, what are you doing?")  # typed while the call is held
    assert run.revoked
    runs.decide(run.id, 1, False)
    assert not await first and run.stopped and run.revoked
    runs.prompt(run, "ok, leave prod alone")
    assert (run.revoked, run.stopped, run.refused) == (False, False, 0)
    # The rejection before the prompt no longer counts: approving a later hold leaves
    # the key open.
    second = asyncio.create_task(runs.hold(run, calls[1], 5, 1))
    await asyncio.sleep(0)
    runs.decide(run.id, calls[1].n, True)
    assert await second and not run.revoked


@pytest.mark.anyio
async def test_a_prompt_during_a_hold_starts_a_new_turn_but_the_key_waits():
    runs, run, calls = _held_pair()
    await _rejected(runs, run, calls[0])
    await _rejected(runs, run, calls[1])
    wait = asyncio.create_task(runs.hold(run, _call(runs, run), 5, 3))
    await asyncio.sleep(0)
    runs.prompt(run, "try something else")  # typed while the call is held
    assert (run.refused, run.revoked) == (0, True)
    assert runs.decide(run.id, 3, False)
    assert not await wait
    assert (run.refused, run.stopped, run.revoked) == (1, False, False)


def test_a_prompt_resets_the_count():
    runs = Runs(EventLog())
    run = runs.get(runs.create(RunIn(task="nettoyer la base")).id)
    assert run is not None
    run.refused = 2
    runs.prompt(run, "try again")
    assert run.refused == 0


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
    }
    assert Message(after=0, text="hi").source == "narration"
    assert TextIn(text="x", source="reasoning").source == "reasoning"
    assert Thresholds().thoughts["R"] == 0.2 and Thresholds().thoughts["about"] == 0.5


def test_the_log_keeps_who_said_it_not_the_reading():
    """A message is logged with its role, never with what the thought reading adds later."""
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
    step = runs.add_step(run, act("Bash", {}), "{}", "write", [], ["agent"])
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


def test_a_session_end_closes_a_message_left_streaming():
    """A session killed mid-message: its message stops streaming and nothing keeps it."""
    runs = Runs(EventLog())
    run = runs.get(runs.create(RunIn(task="nettoyer la base")).id)
    assert run is not None
    runs.stream(run, "m1", "I'll delete the", False)
    runs.disconnect(run)
    # Nothing of it is kept: the same id starts a new message, it doesn't grow the old one.
    runs.stream(run, "m1", "table", True)
    assert [(m.text, m.streaming) for m in run.messages] == [
        ("I'll delete the", False),
        ("table", False),
    ]
