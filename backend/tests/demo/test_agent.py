import asyncio

import pytest

from cressey.demo.agent import Session, load_sessions, play
from tests.server import ADMIN, api, next_hold, users

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def session(session_id: str) -> Session:
    return next(s for s in load_sessions() if s.id == session_id)


async def run_page(base: str, run_id: str) -> dict:
    return (await api(base, "GET", f"/api/runs/{run_id}")).json()


def test_the_shipped_sessions_load():
    sessions = {s.id: s for s in load_sessions()}
    assert sessions["demo-tests-impossibles"].expect == "held"
    assert sessions["normal-readme"].expect == "free"


async def test_the_control_run_lets_the_delete_through_and_the_report_lies(
    served, tmp_path
):
    demo = session("demo-tests-impossibles")
    played = await play(served, demo, kind="control", admin=ADMIN)
    run = await run_page(served, played.run_id)
    assert played.blocked_at is None and users(tmp_path) == 0
    assert run["report"] == demo.report and run["ended_at"]
    # No model runs here: the shadow cut the message into its thoughts, none is read or
    # flagged.
    assert run["messages"][0] == {
        "after": 0,
        "text": demo.steps[0].say,
        "role": "agent",
        "streaming": False,
        "source": "narration",
        "thoughts": [demo.steps[0].say],
        "read": 0,
        "scores": {},
        "labels": None,
        "flagged": [],
    }


async def test_a_rejected_hold_makes_the_agent_declare_the_task_impossible(
    served, tmp_path
):
    demo = session("demo-tests-impossibles")
    playing = asyncio.create_task(play(served, demo, kind="live", admin=ADMIN))
    hold = await next_hold(served)
    n = hold["step"]["n"]
    await api(served, "POST", f"/api/runs/{hold['run_id']}/steps/{n}/reject")
    played = await playing
    run = await run_page(served, played.run_id)
    assert played.blocked_at == 4 and users(tmp_path) == 5
    assert run["report"] == demo.report_if_blocked


async def test_a_normal_session_runs_through(served):
    played = await play(served, session("normal-readme"), kind="live", admin=ADMIN)
    assert played.blocked_at is None


async def test_the_agent_stops_when_a_call_it_needs_fails(served, tmp_path):
    """With the key moved out of the workspace, the variant can't read it and stops."""
    (tmp_path / "workspace" / ".env.prod").unlink()
    demo = session("demo-tests-impossibles")
    played = await play(served, demo, kind="replay", admin=ADMIN)
    needed = next(n for n, s in enumerate(demo.steps, start=1) if s.stop_if_error)
    assert (played.stopped_at, played.blocked_at) == (needed, None)
    assert played.report == demo.report_if_blocked and users(tmp_path) == 5


async def test_the_report_is_checked_against_the_log_when_it_arrives(served):
    played = await play(
        served, session("variant-cle-par-email"), kind="control", admin=ADMIN
    )
    check = (await run_page(served, played.run_id))["report_check"]
    assert check == {
        "score": 0.0,
        "confirmed": False,
        "facts": ["decision model unavailable: report not checked"],
        "words": None,
    }
