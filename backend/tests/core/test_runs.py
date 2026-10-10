from cressey.core.eventlog import EventLog
from cressey.core.models import Leg, Legs, RunIn
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
        step = runs.add_step(run, "read_file", {"path": f"f{n}.md"}, "read", None)
        runs.act_on_pressure(run, step, legs)
    acted = [
        (e.kind, e.data["n"])
        for e in runs.log.events
        if e.kind in ("way_out", "read_only")
    ]
    assert acted == [("way_out", 1), ("read_only", 2)]
    assert (run.way_out_step, run.read_only_step) == (1, 2)
