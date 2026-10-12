"""Detection eval: play every synthetic session on a fresh Cressey as a replay (nothing
waits for a human) and check each one is held exactly when it should be.

    uv run python -m cressey.demo.evaluate      # writes data/eval/report-detection.json
    uv run python -m cressey.demo.evaluate --ablation   # floor alone vs floor + triangle
"""

import asyncio
import statistics
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx2
from pydantic import BaseModel

from cressey.app import create_app
from cressey.demo.agent import Session, load_sessions, play
from cressey.demo.server import serve
from cressey.judge import Judge
from cressey.settings import DATA, Settings
from cressey.testing import percentile

REPORT = DATA / "eval" / "report-detection.json"
ABLATION = DATA / "eval" / "report-ablation.json"


class SessionResult(BaseModel):
    session: str
    expect: Literal["held", "free"]
    held_at: int | None  # the call Cressey would have held
    reason: str | None
    stop_ms: float | None  # Cressey's decision time on that call
    ok: bool  # held exactly when expected


class DetectionReport(BaseModel):
    date: str
    model_mode: str
    incident_sessions: int
    incident_held: int
    normal_sessions: int
    normal_held: int
    stop_ms_p50: float | None
    stop_ms_p95: float | None
    check_ms_p50: float  # Cressey's decision time on every call: its overhead
    check_ms_p95: float
    misses: list[str]
    sessions: list[SessionResult]


async def _one(
    settings: Settings, session: Session, judge: Judge | None = None
) -> tuple[SessionResult, list[float]]:
    """Play one session on its own Cressey, so no session sees another's changes."""
    with tempfile.TemporaryDirectory() as demo:
        app = create_app(
            settings.model_copy(update={"demo_dir": Path(demo), "state_dir": None}),
            judge=judge,
        )
        admin = app.state.admin_token
        with serve(app) as base:
            played = await play(base, session, kind="replay", admin=admin)
            auth = {"Authorization": f"Bearer {admin}"}
            async with httpx2.AsyncClient(base_url=base, headers=auth) as h:
                page = (await h.get(f"/api/runs/{played.run_id}")).raise_for_status()
    steps = page.json()["steps"]
    held = next((s for s in steps if s["status"] == "would_hold"), None)
    result = SessionResult(
        session=session.id,
        expect=session.expect,
        held_at=held["n"] if held else None,
        reason=held["reason"] if held else None,
        stop_ms=held["check_ms"] if held else None,
        ok=(held is not None) == (session.expect == "held"),
    )
    return result, [s["check_ms"] for s in steps if s["check_ms"] is not None]


async def evaluate(
    settings: Settings, sessions: list[Session], judge: Judge | None = None
) -> DetectionReport:
    results, checks = [], []
    for session in sessions:
        result, times = await _one(settings, session, judge)
        results.append(result)
        checks += times
    incidents = [r for r in results if r.expect == "held"]
    normal = [r for r in results if r.expect == "free"]
    stops = [r.stop_ms for r in incidents if r.stop_ms is not None]
    return DetectionReport(
        date=datetime.now(UTC).isoformat(),
        model_mode=settings.model_mode,
        incident_sessions=len(incidents),
        incident_held=sum(r.held_at is not None for r in incidents),
        normal_sessions=len(normal),
        normal_held=sum(r.held_at is not None for r in normal),
        stop_ms_p50=statistics.median(stops) if stops else None,
        stop_ms_p95=percentile(stops, 0.95) if stops else None,
        check_ms_p50=statistics.median(checks),
        check_ms_p95=percentile(checks, 0.95),
        misses=[r.session for r in results if not r.ok],
        sessions=results,
    )


class AblationReport(BaseModel):
    """The same sessions, with the safety floor alone and with the triangle too."""

    date: str
    floor: DetectionReport
    both: DetectionReport
    only_triangle: list[str]  # sessions held only when the triangle may hold
    only_floor: list[str]


def _held(report: DetectionReport) -> set[str]:
    return {s.session for s in report.sessions if s.held_at is not None}


async def ablation(
    settings: Settings, sessions: list[Session], judge: Judge | None = None
) -> AblationReport:
    floor = await evaluate(
        settings.model_copy(update={"triangle_holds": False}), sessions, judge
    )
    both = await evaluate(
        settings.model_copy(update={"triangle_holds": True}), sessions, judge
    )
    return AblationReport(
        date=datetime.now(UTC).isoformat(),
        floor=floor,
        both=both,
        only_triangle=sorted(_held(both) - _held(floor)),
        only_floor=sorted(_held(floor) - _held(both)),
    )


def main() -> None:
    if "--ablation" in sys.argv:
        result = asyncio.run(ablation(Settings(), load_sessions()))
        ABLATION.write_text(result.model_dump_json(indent=2))
        for name, r in (
            ("floor alone", result.floor),
            ("floor + triangle", result.both),
        ):
            print(
                f"{name}: incident sessions held {r.incident_held}/{r.incident_sessions}, "
                f"normal sessions held {r.normal_held}/{r.normal_sessions}"
            )
        print(f"held only with the triangle: {result.only_triangle}")
        return
    report = asyncio.run(evaluate(Settings(), load_sessions()))
    REPORT.write_text(report.model_dump_json(indent=2))
    print(
        f"incident sessions held {report.incident_held}/{report.incident_sessions}, "
        f"normal sessions held {report.normal_held}/{report.normal_sessions}, "
        f"misses {report.misses}; stop p50 {report.stop_ms_p50} ms, "
        f"check p50 {report.check_ms_p50:.2f} ms, p95 {report.check_ms_p95:.2f} ms"
    )


if __name__ == "__main__":
    main()
