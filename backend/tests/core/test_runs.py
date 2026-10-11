import asyncio

import pytest
from pydantic import JsonValue

from cressey.core.eventlog import EventLog
from cressey.core.models import Leg, Legs, Run, RunIn, Step
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


async def _rejected(runs: Runs, run: Run, step: Step, stop_after: int = 3) -> None:
    """A call held, then rejected by a human."""
    wait = asyncio.create_task(runs.hold(run, step, 5, stop_after))
    await asyncio.sleep(0)
    assert runs.decide(run.id, step.n, False)
    assert not await wait


def _call(runs: Runs, run: Run) -> Step:
    return runs.add_step(run, "run_sql", {"q": "x"}, "x", "destructive", "hors mandat")


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
    assert runs.log.events[-1].kind == "unlocked"


@pytest.mark.anyio
async def test_unlock_leaves_the_key_suspended_while_a_call_is_held():
    runs, run, calls = _held_pair()
    wait = asyncio.create_task(runs.hold(run, calls[0], 5, 3))
    await asyncio.sleep(0)
    runs.unlock(run)
    assert run.revoked
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
