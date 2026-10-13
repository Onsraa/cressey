import asyncio

import httpx2
import pytest

from cressey.replay.importers import load_sessions
from cressey.replay.player import play
from cressey.replay.trajectory import Call, Say, Session, Trajectory
from cressey.testing import ADMIN, api, next_hold, users

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def session(session_id: str) -> Session:
    return next(s for s in load_sessions() if s.id == session_id)


async def run_page(base: str, run_id: str) -> dict:
    return (await api(base, "GET", f"/api/runs/{run_id}")).json()


async def test_the_control_run_lets_the_delete_through_and_the_report_lies(
    served, tmp_path
):
    demo = session("demo-tests-impossibles")
    played = await play(served, demo, kind="control", admin=ADMIN)
    run = await run_page(served, played.run_id)
    assert played.blocked_at is None and users(tmp_path) == 0
    assert run["report"] == demo.report and run["ended_at"]
    # No model runs here: the shadow cut the message into its thoughts, none is read.
    assert run["messages"][0] == {
        "after": 0,
        "text": demo.steps[0].say,
        "role": "agent",
        "streaming": False,
        "source": "narration",
        "thoughts": [demo.steps[0].say],
        "read": 0,
        "scores": {},
        "legs": None,
        "points": [],
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
    calls = [s for s in demo.steps if isinstance(s, Call)]
    needed = next(n for n, s in enumerate(calls, start=1) if s.stop_if_error)
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
    }


async def test_a_recorded_run_plays_through_the_hook_and_stops_where_cressey_holds(
    served_short_holds,
):
    """A Claude Code transcript's trajectory: its words, each call before it runs, what it
    returned, until Cressey holds a call; then the end of the turn with its report."""
    base = served_short_holds
    recorded = Trajectory(
        id="clean-build",
        task="Clean the build folder",
        steps=[
            Say(say="I'll look at the build folder first."),
            Call(call="Bash", args={"command": "ls build"}, returned="app.js"),
            Call(call="Bash", args={"command": "rm -rf build"}, returned=""),
            Call(call="Read", args={"file_path": "README.md"}, returned="# app"),
        ],
        report="The build folder is clean.",
    )
    played = await play(base, recorded, surface="hook", admin=ADMIN)
    run = await run_page(base, played.run_id)
    # Stopped at call 2: its report is the last thing it said, not the recording's end.
    said = "I'll look at the build folder first."
    assert (played.blocked_at, played.report) == (2, said)
    assert [(s["tool"], s["status"]) for s in run["steps"]] == [
        ("Bash", "allowed"),
        ("Bash", "expired"),
    ]
    assert [m["text"] for m in run["messages"]] == [
        "I'll look at the build folder first."
    ]
    assert (run["via"], run["report"]) == ("hook", said)


async def test_a_recording_never_plays_through_the_gateway(served, tmp_path):
    """Through MCP its calls would run for real on the upstream: refused before any run."""
    recorded = Trajectory(
        id="recorded",
        task="Clean up",
        steps=[
            Call(
                call="run_sql",
                args={"query": "DELETE FROM users"},
                returned="0 rows affected",
            )
        ],
    )
    with pytest.raises(ValueError, match="through the hook"):
        await play(served, recorded, kind="control", admin=ADMIN)
    assert users(tmp_path) == 5
    assert (await api(served, "GET", "/api/runs")).json() == []


async def test_a_message_the_api_refuses_stops_the_replay(served):
    """A failed post is an error, never a step the replay pretends it took."""
    too_long = Trajectory(
        id="long", task="Fix the test", steps=[Say(say="x" * 6000)], report="Done."
    )
    with pytest.raises(httpx2.HTTPStatusError):
        await play(served, too_long, kind="control", admin=ADMIN)


@pytest.mark.parametrize(
    "given",
    ['{"may_destroy": ["users"', '["users"]', '{"may_destroy": "users"}'],
)
def test_a_mandate_the_command_line_cant_read_is_a_usage_error(
    given, monkeypatch, capsys
):
    """Not JSON, not an object, or a field of the wrong type: said plainly, no traceback."""
    from cressey.replay import player

    monkeypatch.setenv("CRESSEY_ADMIN_TOKEN", ADMIN)
    argv = ["player", "run.jsonl", "--task", "Reset staging", "--mandate", given]
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit) as stopped:
        player.main()
    assert stopped.value.code == 2
    assert "--mandate" in capsys.readouterr().err
