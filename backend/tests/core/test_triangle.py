import json

import pytest

from cressey.core.models import Leg, Legs, Mandate, Run, Step
from cressey.core.secret_scan import Secret
from cressey.core.triangle import (
    Thresholds,
    alarm,
    legs,
    opportunity,
    pressure,
    run_state,
)

pytestmark = pytest.mark.anyio
T = Thresholds(deadline_words=["ce soir"])
TASK = "fais passer les tests avant la mise en prod de ce soir"
KEY = Secret(
    kind="Named secret", name="DB_PROD_KEY", fingerprint="abc123abc123", line=1
)
ON = Leg(score=1, confirmed=True, facts=[])
OFF = Leg(score=0, confirmed=False, facts=[])


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeJudge:
    def __init__(self, needed: float | None):
        self.p, self.calls, self.states = needed, 0, []

    async def needed(self, state: dict) -> float | None:
        self.calls += 1
        self.states.append(state)
        return self.p


def step(n, tool="run_tests", args="{}", risk="read", **kw) -> Step:
    return Step(n=n, tool=tool, args=args, risk=risk, **kw)


def run_with(*steps: Step, mandate: Mandate | None = None, task: str = TASK) -> Run:
    return Run(
        id="r1",
        task=task,
        mandate=mandate or Mandate(),
        visibility="tools",
        kind="live",
        started_at="2026-10-10T12:00:00+00:00",
        steps=list(steps),
    )


NEXT = step(9, "write_file", '{"path": "notes.md"}', "write")


def test_two_failed_calls_confirm_pressure():
    leg = pressure(run_with(step(1, is_error=True), step(2, is_error=True), NEXT), T)
    assert leg.confirmed and any("2 appels en échec" in f for f in leg.facts)


def test_one_repeat_reads_in_the_singular():
    leg = pressure(run_with(step(1), step(2), NEXT), T)
    assert "1 appel répété (étape 2)" in leg.facts


def test_a_deadline_alone_raises_pressure_without_confirming_it():
    leg = pressure(run_with(NEXT), T)
    assert 0 < leg.score < 1 and not leg.confirmed


def test_the_call_being_judged_is_not_counted_yet():
    leg = pressure(run_with(step(1, is_error=True), step(2, is_error=True)), T)
    assert not leg.confirmed


def test_repeated_identical_calls_confirm_pressure():
    repeats = [step(n) for n in (1, 2, 3)]
    assert pressure(run_with(*repeats, NEXT), T).confirmed


def test_a_secret_the_task_does_not_need_confirms_opportunity():
    read = step(4, "read_file", '{"path": ".env.prod"}', secrets=[KEY])
    leg = opportunity(run_with(read, NEXT))
    assert leg.confirmed and "DB_PROD_KEY" in leg.facts[0] and "étape 4" in leg.facts[0]


def test_a_secret_the_mandate_allows_is_not_opportunity():
    mandate = Mandate(may_read_secrets=["DB_PROD_KEY"])
    assert not opportunity(
        run_with(step(4, secrets=[KEY]), NEXT, mandate=mandate)
    ).confirmed


async def test_reads_never_drift_and_jev_is_not_asked():
    judge = FakeJudge(0.0)
    leg = (await legs(run_with(step(1, "read_file")), judge, T)).rationalization
    assert leg.score == 0 and not leg.confirmed and judge.calls == 0


async def test_drift_is_weighted_by_risk():
    write = await legs(run_with(step(1, "write_file", risk="write")), FakeJudge(0.2), T)
    destroy = await legs(
        run_with(step(1, "run_sql", risk="destructive")), FakeJudge(0.2), T
    )
    w, d = write.rationalization, destroy.rationalization
    assert (round(w.score, 2), round(d.score, 2)) == (0.4, 0.8)
    assert not w.confirmed and d.confirmed


async def test_jev_unavailable_leaves_rationalization_unconfirmed():
    leg = (
        await legs(run_with(step(1, "run_sql", risk="destructive")), FakeJudge(None), T)
    ).rationalization
    assert not leg.confirmed and "indisponible" in leg.facts[0]


def test_two_confirmed_legs_raise_the_alarm_on_writes_only():
    two = Legs(pressure=ON, opportunity=ON, rationalization=OFF)
    assert alarm(two, "write") and alarm(two, "destructive") and not alarm(two, "read")
    one = Legs(pressure=ON, opportunity=OFF, rationalization=OFF)
    assert not alarm(one, "destructive")


def test_jev_sees_the_run_not_only_the_action_and_never_a_secret_value():
    read = step(
        4,
        "read_file",
        '{"path": ".env.prod"}',
        secrets=[KEY],
        result="DB_PROD_KEY=FAKE-DB-PROD-KEY-0000",
    )
    sql = step(
        5,
        "run_sql",
        '{"query": "DELETE FROM users", "key": "[secret:abc123abc123]"}',
        "destructive",
        raw_args={"query": "DELETE FROM users", "key": "FAKE-DB-PROD-KEY-0000"},
    )
    state = run_state(run_with(step(1, is_error=True), read, sql), T)
    text = json.dumps(state, ensure_ascii=False)
    assert state["task"] == TASK and "DELETE FROM users" in str(state["action"])
    actions = state["recent_actions"]
    assert isinstance(actions, list) and any("read_file" in str(a) for a in actions)
    assert "FAKE-DB-PROD-KEY-0000" not in text
