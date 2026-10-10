"""« Rejouer ×5 »: the incident's session and its variants, then every normal session, each
played again on a fresh Cressey with the approved fixes applied. A regression test of the
policy and the fixes on scripted sessions: it says nothing of how a real agent behaves."""

import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx2
from fastapi import FastAPI

from cressey.core.models import Fix, Replay, ReplayResult
from cressey.demo.agent import Session, play
from cressey.demo.server import serve

# A fresh Cressey whose demo state lives in that folder.
MakeApp = Callable[[Path], FastAPI]


def family(sessions: list[Session], task: str) -> list[Session]:
    """The incident session with this task, then the sessions that vary it."""
    roots = [
        s
        for s in sessions
        if s.expect == "held" and not s.variant_of and s.task == task
    ]
    ids = {s.id for s in roots}
    return roots + [s for s in sessions if s.variant_of in ids]


def _apply(fixes: list[Fix], session: Session, demo: Path) -> Session:
    work = (demo / "workspace").resolve()  # where demo_tools keeps the agent's files
    for name in (n for f in fixes for n in f.move_out):
        target = (work / name).resolve()
        if target.is_relative_to(work):  # the names come from the agent's own calls
            target.unlink(missing_ok=True)
    added = [f.add_to_task for f in fixes if f.add_to_task]
    return session.model_copy(update={"task": " ".join([session.task, *added])})


async def _one(make_app: MakeApp, session: Session, fixes: list[Fix]) -> ReplayResult:
    with tempfile.TemporaryDirectory() as tmp:
        demo = Path(tmp)
        app = make_app(demo)  # seeds the demo state, which the fixes then change
        fixed = _apply(fixes, session, demo)
        with serve(app) as base:
            played = await play(base, fixed, kind="replay")
            async with httpx2.AsyncClient(base_url=base) as h:
                run = (await h.get(f"/api/runs/{played.run_id}")).raise_for_status()
    steps = {s["n"]: s for s in run.json()["steps"]}
    if played.blocked_at is not None:
        outcome, step = "refused", played.blocked_at
        reason = steps.get(step, {}).get("reason")
    elif played.stopped_at is not None:
        outcome, step, reason = "stopped", played.stopped_at, None
    else:
        outcome, step, reason = "completed", None, None
    return ReplayResult(
        session=session.id,
        expect=session.expect,
        outcome=outcome,
        step=step,
        reason=reason,
        ok=outcome == ("stopped" if session.expect == "held" else "completed"),
    )


async def replay(
    make_app: MakeApp, fixes: list[Fix], task: str, sessions: list[Session]
) -> Replay:
    approved = [f for f in fixes if f.approved]
    played = family(sessions, task) + [s for s in sessions if s.expect == "free"]
    results = [await _one(make_app, s, approved) for s in played]
    return Replay(
        date=datetime.now(UTC).isoformat(),
        fixes=[f.leg for f in approved],
        results=results,
        passed=any(r.expect == "held" for r in results) and all(r.ok for r in results),
    )
