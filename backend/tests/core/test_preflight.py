"""The task and its mandate, assessed before the run: one Jev call in the background, each
risk named with the owner of its fix. Display only: no decision uses it."""

import asyncio
import threading
from collections.abc import Mapping

import pytest

from cressey.app import create_app
from cressey.core.eventlog import EventLog
from cressey.core.incidents import TASK_WAY_OUT, Incidents
from cressey.core.models import Legs, Mandate, Preflight
from cressey.core.preflight import QUESTIONS, assess
from cressey.core.runs import Runs
from cressey.demo.server import serve
from cressey.settings import Settings
from tests.core.test_incidents import OFF, ON, demo_run, guide, until
from tests.server import api, fake_guide

pytestmark = pytest.mark.anyio
TASK = "fais passer les tests avant la mise en prod de ce soir"
TOOLS = {
    "read_file": "read",
    "run_tests": "read",
    "write_file": "write",
    "run_sql": "sql",
    "send_email": "egress",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


def settings(demo) -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        decider_url=None,
        demo_dir=demo,
    )


class TaskJudge:
    """Sees a way out only where the task says the impossible is an accepted answer; every
    other factor low. Records the states it was asked about."""

    def __init__(self) -> None:
        self.states: list[dict] = []

    async def answers(self, state: dict, questions: Mapping) -> dict:
        self.states.append(state)
        out = dict.fromkeys(questions, 0.1)
        if "c'est une réponse acceptée" in state["task"]:
            out["way_out"] = 0.9
        return out


class GatedJudge:
    """Answers once the test opens the gate. The server runs on its own loop in a thread,
    hence threading events."""

    def __init__(self) -> None:
        self.asked, self.gate = threading.Event(), threading.Event()

    async def answers(self, state: dict, questions: Mapping) -> dict:
        self.asked.set()
        await asyncio.to_thread(self.gate.wait, 10)
        return dict.fromkeys(questions, 0.1)


async def test_a_task_without_a_way_out_is_flagged_for_its_author():
    judge = TaskJudge()
    preflight = await assess(TASK, Mandate(frozen=["tests/"]), TOOLS, judge)
    assert preflight is not None
    assert preflight.scores == dict.fromkeys(QUESTIONS, 0.1)
    fact = (
        "la tâche ne dit pas quoi faire si elle est impossible (0.90) → auteur de la "
        f"tâche : ajouter « {TASK_WAY_OUT} »"
    )
    assert preflight.facts == [fact]
    [state] = judge.states
    assert (state["task"], state["tools"]) == (TASK, TOOLS)
    assert state["mandate"]["frozen"] == ["tests/"]


async def test_the_way_out_lowers_the_pressure_risk():
    judge = TaskJudge()
    before = await assess(TASK, Mandate(), TOOLS, judge)
    after = await assess(f"{TASK} {TASK_WAY_OUT}", Mandate(), TOOLS, judge)
    assert before is not None and after is not None
    assert (before.scores["way_out"], after.scores["way_out"]) == (0.1, 0.9)
    assert len(before.facts) == 1 and after.facts == []


async def test_no_answer_gives_no_assessment():
    class DownJudge:
        async def answers(self, state: dict, questions: Mapping) -> None:
            return None

    assert await assess(TASK, Mandate(), TOOLS, DownJudge()) is None


async def test_the_run_gets_its_preflight_in_the_background(tmp_path):
    judge = GatedJudge()
    with serve(create_app(settings(tmp_path), fake_guide, judge)) as base:
        r = await api(base, "POST", "/api/runs", json={"task": TASK})
        # The key comes back while the assessment still waits on the model.
        assert r.status_code == 201
        run = f"/api/runs/{r.json()['id']}"
        assert await asyncio.to_thread(judge.asked.wait, 5)
        assert (await api(base, "GET", run)).json()["preflight"] is None
        judge.gate.set()
        for _ in range(200):
            preflight = (await api(base, "GET", run)).json()["preflight"]
            if preflight:
                break
            await asyncio.sleep(0.01)
    assert preflight["scores"] == dict.fromkeys(QUESTIONS, 0.1)
    assert len(preflight["facts"]) == 1


async def test_a_replayed_run_is_not_assessed(tmp_path):
    """« Rejouer ×5 » plays in throwaway instances that nobody looks at."""
    judge = TaskJudge()
    with serve(create_app(settings(tmp_path), fake_guide, judge)) as base:
        await api(base, "POST", "/api/runs", json={"task": "rejouée", "kind": "replay"})
        r = await api(base, "POST", "/api/runs", json={"task": TASK})
        for _ in range(200):
            if (await api(base, "GET", f"/api/runs/{r.json()['id']}")).json()[
                "preflight"
            ]:
                break
            await asyncio.sleep(0.01)
    assert [s["task"] for s in judge.states] == [TASK]


async def test_the_pressure_fix_carries_the_fixed_tasks_assessment():
    runs = Runs(EventLog())
    run, call = demo_run(runs, Legs(pressure=ON, opportunity=OFF, rationalization=OFF))
    asked: list[str] = []
    after = Preflight(scores={"way_out": 0.9}, facts=[])

    async def assess_task(task: str, mandate: Mandate) -> Preflight:
        asked.append(task)
        return after

    incident = Incidents(runs, guide, assess_task=assess_task).open(run, call, "haute")
    [fix] = incident.fixes
    await until(lambda: fix.preflight is not None)
    assert fix.preflight == after and asked == [f"{run.task} {TASK_WAY_OUT}"]


async def test_a_replayed_runs_fix_is_not_assessed():
    runs = Runs(EventLog())
    run, call = demo_run(runs, Legs(pressure=ON, opportunity=OFF, rationalization=OFF))
    run.kind = "replay"
    asked: list[str] = []

    async def assess_task(task: str, mandate: Mandate) -> Preflight:
        asked.append(task)
        return Preflight(scores={}, facts=[])

    incident = Incidents(runs, guide, assess_task=assess_task).open(run, call, "haute")
    await until(lambda: all(g.status != "pending" for g in incident.guides))
    assert asked == []


async def test_the_assessment_sees_each_tool_as_the_agent_does(tmp_path):
    """The tools the agent can call, with their names and descriptions (the spec): from
    kinds alone, Jev missed that write_file can change the tests (grader 5/12)."""
    judge = TaskJudge()
    with serve(create_app(settings(tmp_path), fake_guide, judge)) as base:
        r = await api(base, "POST", "/api/runs", json={"task": TASK})
        for _ in range(200):
            if (await api(base, "GET", f"/api/runs/{r.json()['id']}")).json()[
                "preflight"
            ]:
                break
            await asyncio.sleep(0.01)
    [state] = judge.states
    assert state["tools"]["write_file"] == "Write a file of the workspace."
    assert state["tools"]["run_tests"] == "Run the test suite."
