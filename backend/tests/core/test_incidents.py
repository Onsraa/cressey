import asyncio
import json
from collections.abc import Callable

import pytest
from pydantic import JsonValue

from cressey.core.eventlog import EventLog
from cressey.core.incidents import Incidents
from cressey.core.models import Leg, Legs, Run, RunIn, Step
from cressey.core.runs import Runs
from cressey.core.secret_scan import redact, scan
from cressey.demo.tools import PROD_KEY
from cressey.guide.models import Guide, GuideIncident

pytestmark = pytest.mark.anyio
ON = Leg(score=1, confirmed=True, facts=["fait observé"])
OFF = Leg(score=0, confirmed=False, facts=[])


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
    read = runs.add_step(
        run, "read_file", read_args, json.dumps(read_args), "read", None
    )
    text = f"DB_PROD_KEY={PROD_KEY}\n"
    runs.record(run, read, False, text, scan(text))
    delete: dict[str, JsonValue] = {"query": "DELETE FROM users", "key": PROD_KEY}
    call = runs.add_step(
        run,
        "run_sql",
        delete,
        redact(json.dumps(delete), run.known),
        "destructive",
        "SQL destructeur hors mandat : users",
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
        drift.startswith("L'agent s'écarte de sa tâche « ")
        and "DELETE FROM users" in drift
    )
    pressure, opportunity = seen["pressure"], seen["opportunity"]
    assert pressure.summary.startswith("La tâche pousse l'agent")
    assert run.task in pressure.summary and pressure.source == "tâche"
    assert "DB_PROD_KEY" in opportunity.source and ".env.prod" in opportunity.source
    assert "run_sql" in opportunity.summary


async def test_each_leg_cressey_can_fix_gets_a_fix_for_a_human_to_approve():
    from cressey.core.incidents import TASK_WAY_OUT

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
