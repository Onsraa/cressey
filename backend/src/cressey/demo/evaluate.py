"""Detection eval: play every synthetic session on a fresh Cressey as a replay (nothing
waits for a human) and check each one is held exactly when it should be.

    uv run python -m cressey.demo.evaluate      # writes data/eval/report-detection.json
"""

import asyncio
import statistics
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx2
from pydantic import BaseModel

from cressey.app import create_app
from cressey.demo.agent import Session, load_sessions, play
from cressey.demo.server import serve
from cressey.guide.corpus import DATA
from cressey.settings import Settings

REPORT = DATA / "eval" / "report-detection.json"


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


def _p95(values: list[float]) -> float:
    return statistics.quantiles(values, n=20)[-1] if len(values) > 1 else values[0]


async def _one(
    settings: Settings, session: Session
) -> tuple[SessionResult, list[float]]:
    """Play one session on its own Cressey, so no session sees another's changes."""
    with tempfile.TemporaryDirectory() as demo:
        app = create_app(settings.model_copy(update={"demo_dir": Path(demo)}))
        with serve(app) as base:
            played = await play(base, session, kind="replay")
            async with httpx2.AsyncClient(base_url=base) as h:
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


async def evaluate(settings: Settings, sessions: list[Session]) -> DetectionReport:
    results, checks = [], []
    for session in sessions:
        result, times = await _one(settings, session)
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
        stop_ms_p95=_p95(stops) if stops else None,
        check_ms_p50=statistics.median(checks),
        check_ms_p95=_p95(checks),
        misses=[r.session for r in results if not r.ok],
        sessions=results,
    )


def main() -> None:
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
