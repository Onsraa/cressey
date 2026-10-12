import asyncio
import json
from collections.abc import Callable

import pytest
from pydantic import JsonValue

from cressey.demo.tools import PROD_KEY
from cressey.domain.guides import Guide, GuideIncident
from cressey.domain.reasons import Reason
from cressey.domain.runs import Leg, Legs, Run, RunIn, Step
from cressey.incidents.incidents import Incidents
from cressey.scan.secrets import redact, scan
from cressey.store.eventlog import EventLog
from cressey.store.runs import Runs

pytestmark = pytest.mark.anyio
ON = Leg(score=1, confirmed=True, facts=["fait observé"])
OFF = Leg(score=0, confirmed=False, facts=[])
SQL_USERS = Reason(check="destructive_sql", target="users")


@pytest.fixture
def anyio_backend():
    return "asyncio"


def guide(gi: GuideIncident) -> Guide:
    return Guide(
        id=f"g-{gi.id}",
        incident_id=gi.id,
        status="ok",
        message=None,
        steps=[],
        passages=[],
        dropped_steps=0,
    )


def demo_run(runs: Runs, legs: Legs) -> tuple[Run, Step]:
    """The agent reads the production key, then uses it in a DELETE."""
    created = runs.create(RunIn(task="fais passer les tests avant la mise en prod"))
    run = runs.get(created.id)
    assert run is not None
    read_args: dict[str, JsonValue] = {"path": ".env.prod"}
    read = runs.add_step(run, "read_file", read_args, json.dumps(read_args), "read", [])
    text = f"DB_PROD_KEY={PROD_KEY}\n"
    runs.record(run, read, False, text, scan(text))
    delete: dict[str, JsonValue] = {"query": "DELETE FROM users", "key": PROD_KEY}
    call = runs.add_step(
        run,
        "run_sql",
        delete,
        redact(json.dumps(delete), run.known),
        "destructive",
        [SQL_USERS],
    )
    call.legs = legs
    return run, call


async def until(done: Callable[[], bool]) -> None:
    for _ in range(200):
        if done():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("not settled")


async def test_an_incident_traces_the_key_to_where_it_was_read():
    runs = Runs(EventLog())
    run, call = demo_run(runs, Legs(pressure=OFF, opportunity=ON, rationalization=OFF))
    incident = Incidents(runs, guide).open(run, call, "critique")
    [source] = incident.sources
    assert (source.step, source.tool, source.how, source.secret) == (
        1,
        "read_file",
        "exact",
        "DB_PROD_KEY",
    )
    assert PROD_KEY not in incident.model_dump_json()


async def test_each_confirmed_leg_gets_a_guide_for_its_owner():
    runs = Runs(EventLog())
    run, call = demo_run(runs, Legs(pressure=ON, opportunity=ON, rationalization=OFF))
    incident = Incidents(runs, guide).open(run, call, "critique")
    assert [(g.leg, g.owner_role) for g in incident.guides] == [
        ("pressure", "task_author"),
        ("opportunity", "key_owner"),
    ]


async def test_a_safety_floor_hit_without_a_confirmed_leg_goes_to_the_soc():
    runs = Runs(EventLog())
    run, call = demo_run(runs, Legs(pressure=OFF, opportunity=OFF, rationalization=OFF))
    incident = Incidents(runs, guide).open(run, call, "critique")
    assert [(g.leg, g.owner_role) for g in incident.guides] == [
        ("rationalization", "soc")
    ]


async def test_guides_are_written_in_the_background_and_never_see_a_secret():
    seen: list[GuideIncident] = []

    def spy(gi: GuideIncident) -> Guide:
        seen.append(gi)
        return guide(gi)

    runs = Runs(EventLog())
    run, call = demo_run(runs, Legs(pressure=ON, opportunity=ON, rationalization=OFF))
    incident = Incidents(runs, spy).open(run, call, "critique")
    assert {g.status for g in incident.guides} == {"pending"}
    await until(lambda: all(g.status == "ok" for g in incident.guides))
    assert [g.guide_id for g in incident.guides] == [
        f"g-{incident.id}-pressure",
        f"g-{incident.id}-opportunity",
    ]
    assert len(seen) == 2 and all(PROD_KEY not in gi.model_dump_json() for gi in seen)


async def test_a_guide_that_fails_is_marked_unavailable():
    def broken(gi: GuideIncident) -> Guide:
        raise RuntimeError("pipeline down")

    runs = Runs(EventLog())
    run, call = demo_run(runs, Legs(pressure=ON, opportunity=OFF, rationalization=OFF))
    incident = Incidents(runs, broken).open(run, call, "critique")
    await until(lambda: incident.guides[0].status == "unavailable")


async def test_the_queue_puts_critical_incidents_first_then_the_oldest():
    runs = Runs(EventLog())
    incidents = Incidents(runs, guide)
    legs = Legs(pressure=ON, opportunity=ON, rationalization=OFF)
    first = incidents.open(*demo_run(runs, legs), "haute")
    second = incidents.open(*demo_run(runs, legs), "critique")
    third = incidents.open(*demo_run(runs, legs), "haute")
    assert [i.id for i in incidents.all()] == [second.id, first.id, third.id]


async def test_the_incident_shows_the_decision_on_its_call():
    runs = Runs(EventLog())
    incidents = Incidents(runs, guide)
    run, call = demo_run(runs, Legs(pressure=ON, opportunity=ON, rationalization=OFF))
    incident = incidents.open(run, call, "critique")
    call.status = "approved"
    shown = incidents.get(incident.id)
    assert shown is not None and shown.decision == "approved"


async def test_each_guide_gets_a_root_cause_sentence_for_its_leg():
    seen: dict[str, GuideIncident] = {}

    def spy(gi: GuideIncident) -> Guide:
        seen[gi.leg] = gi
        return guide(gi)

    runs = Runs(EventLog())
    run, call = demo_run(runs, Legs(pressure=ON, opportunity=ON, rationalization=ON))
    Incidents(runs, spy).open(run, call, "critique")
    await until(lambda: len(seen) == 3)
    drift = seen["rationalization"].summary
    assert (
        drift.startswith("The agent strays from its task “")
        and "DELETE FROM users" in drift
    )
    pressure, opportunity = seen["pressure"], seen["opportunity"]
    assert pressure.summary.startswith("The task pushes the agent")
    assert run.task in pressure.summary and pressure.source == "task"
    assert "DB_PROD_KEY" in opportunity.source and ".env.prod" in opportunity.source
    assert "run_sql" in opportunity.summary


async def test_each_leg_cressey_can_fix_gets_a_fix_for_a_human_to_approve():
    from cressey.engine.agent_text import TASK_WAY_OUT

    runs = Runs(EventLog())
    run, call = demo_run(runs, Legs(pressure=ON, opportunity=ON, rationalization=ON))
    incident = Incidents(runs, guide).open(run, call, "critique")
    fixes = {f.leg: f for f in incident.fixes}
    assert set(fixes) == {"pressure", "opportunity"}  # rationalization: its guide only
    key, task = fixes["opportunity"], fixes["pressure"]
    assert (key.owner_role, key.move_out, key.approved) == (
        "key_owner",
        [".env.prod"],
        False,
    )
    assert "DB_PROD_KEY" in key.text and ".env.prod" in key.text
    assert (task.owner_role, task.add_to_task) == ("task_author", TASK_WAY_OUT)
    assert TASK_WAY_OUT in task.text


async def test_a_leg_left_unconfirmed_gets_no_fix():
    runs = Runs(EventLog())
    run, call = demo_run(runs, Legs(pressure=OFF, opportunity=ON, rationalization=OFF))
    incident = Incidents(runs, guide).open(run, call, "critique")
    assert [f.leg for f in incident.fixes] == ["opportunity"]


def held_by_floor(runs: Runs, reason: Reason = SQL_USERS) -> tuple[Run, Step]:
    """A new run whose DELETE the floor held."""
    run, call = demo_run(runs, Legs(pressure=OFF, opportunity=OFF, rationalization=OFF))
    call.because([reason])
    return run, call


async def test_runs_going_after_the_same_target_raise_a_fleet_signal():
    """Hugging Face / METR: hundreds of agents hit the same target; one run looks normal."""
    from cressey.domain.policy import Fleet

    runs = Runs(EventLog())
    incidents = Incidents(runs, guide, fleet=Fleet(runs=3, window_minutes=15))
    first, second, third = (
        incidents.open(*held_by_floor(runs), "critique") for _ in range(3)
    )
    [signal] = incidents.fleet()
    assert signal.checks == ["destructive_sql"]
    assert signal.target == "run_sql | destructive SQL outside the mandate: users"
    assert signal.runs == [first.run_id, second.run_id, third.run_id]
    assert [e.kind for e in runs.log.events].count("fleet_signal") == 1


async def test_one_run_held_again_and_again_is_not_a_fleet():
    from cressey.domain.policy import Fleet

    runs = Runs(EventLog())
    incidents = Incidents(runs, guide, fleet=Fleet(runs=3, window_minutes=15))
    run, call = held_by_floor(runs)
    for _ in range(3):
        incidents.open(run, call, "critique")
    incidents.open(
        *held_by_floor(runs, Reason(check="egress", target="x@prestataire.example")),
        "critique",
    )
    assert incidents.fleet() == []


async def test_holds_older_than_the_window_dont_count():
    from datetime import UTC, datetime, timedelta

    from cressey.domain.policy import Fleet

    runs = Runs(EventLog())
    incidents = Incidents(runs, guide, fleet=Fleet(runs=2, window_minutes=15))
    incidents.clock = lambda: datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    incidents.open(*held_by_floor(runs), "critique")
    incidents.clock = lambda: (
        datetime(2026, 10, 10, 12, 0, tzinfo=UTC) + timedelta(minutes=16)
    )
    incidents.open(*held_by_floor(runs), "critique")
    assert incidents.fleet() == []
