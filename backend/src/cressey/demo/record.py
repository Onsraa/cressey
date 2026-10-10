"""Record the stage cache in one command, then check it offline.

    cd backend && CRESSEY_MODEL_MODE=record uv run python -m cressey.demo.record --fresh

Every model answer the demo needs goes into data/cache: the triangle on every shipped session
(the detection eval and the ablation); each incident session played live, its hold rejected
and its guides written, its « Rejouer ×5 » before a fix, with the key fix, and with every
fix, and its Observer run; and the guide eval. Then the same plays run again in a child
process in `replay` mode, with the keys blanked: they must give the same results.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx2

from cressey.app import create_app
from cressey.demo.agent import Session, load_sessions, play
from cressey.demo.evaluate import ABLATION, REPORT, ablation, evaluate
from cressey.demo.server import serve
from cressey.guide.api import write_guide
from cressey.guide.corpus import DATA
from cressey.guide.models import Guide, GuideIncident
from cressey.settings import Settings

FLOWS = DATA / "eval" / "record-flows.json"  # what the recorded incident flows gave
_ONE_GUIDE = threading.Lock()


def _one_at_a_time(gi: GuideIncident) -> Guide:
    """Guides one after another: a burst of model calls could be throttled, and lost."""
    with _ONE_GUIDE:
        return write_guide(gi)


async def _until[T](
    check: Callable[[], Awaitable[T | None]], seconds: float = 180
) -> T:
    for _ in range(int(seconds * 10)):
        if (got := await check()) is not None:
            return got
        await asyncio.sleep(0.1)
    raise SystemExit("record: timed out waiting")


async def incident_flow(settings: Settings, session: Session) -> dict:
    """One incident session as on stage: held and rejected, guides written, « Rejouer ×5 »
    before any fix, with the key fix, then with every fix, and the Observer run."""
    with tempfile.TemporaryDirectory() as tmp:
        live_settings = settings.model_copy(update={"demo_dir": Path(tmp)})
        app = create_app(live_settings, make_guide=_one_at_a_time)
        with serve(app) as base:
            async with httpx2.AsyncClient(base_url=base, timeout=300) as h:
                live = asyncio.create_task(play(base, session, kind="live"))

                async def held() -> dict | None:
                    holds = (await h.get("/api/holds")).json()
                    return holds[0] if holds else None

                hold = await _until(held)
                n = hold["step"]["n"]
                await h.post(f"/api/runs/{hold['run_id']}/steps/{n}/reject")
                await live
                [first] = (await h.get("/api/incidents")).json()
                path = f"/api/incidents/{first['id']}"

                async def written() -> dict | None:
                    i = (await h.get(path)).json()
                    return (
                        i
                        if all(g["status"] != "pending" for g in i["guides"])
                        else None
                    )

                incident = await _until(written)
                replays = {"none": (await h.post(f"{path}/replay")).json()["passed"]}
                legs = [f["leg"] for f in incident["fixes"]]
                for leg in sorted(legs, key=lambda leg: leg != "opportunity"):
                    await h.post(f"{path}/fixes/{leg}/approve")
                    replays["+" + leg] = (await h.post(f"{path}/replay")).json()[
                        "passed"
                    ]
            control = await play(base, session, kind="control")
    return {
        "session": session.id,
        "guides": {g["leg"]: g["status"] for g in incident["guides"]},
        "replay_passed": replays,
        "control_blocked_at": control.blocked_at,
    }


async def plays(settings: Settings) -> dict:
    sessions = load_sessions()
    roots = [s for s in sessions if s.expect == "held" and not s.variant_of]
    detection = await evaluate(settings, sessions)
    both = await ablation(settings, sessions)
    flows = [await incident_flow(settings, s) for s in roots]
    return {
        "detection": {
            "incident_held": detection.incident_held,
            "normal_held": detection.normal_held,
            "misses": detection.misses,
        },
        "ablation_only_triangle": both.only_triangle,
        "flows": flows,
        "_reports": (detection, both),
    }


def record(fresh: bool) -> None:
    s = Settings()
    if s.model_mode != "record":
        raise SystemExit("record: run with CRESSEY_MODEL_MODE=record")
    if fresh:
        for f in s.cache_dir.glob("*/*.json"):
            f.unlink()
    elif any(s.cache_dir.glob("*/*.json")):
        raise SystemExit("record: the cache isn't empty; pass --fresh to start it over")
    got = asyncio.run(plays(s))
    detection, both = got.pop("_reports")
    REPORT.write_text(detection.model_dump_json(indent=2))
    ABLATION.write_text(both.model_dump_json(indent=2))
    from cressey.guide.api import get_pipeline
    from cressey.guide.eval import evaluate as guide_eval
    from cressey.guide.retrieve import Retriever

    pipe = get_pipeline()
    if not isinstance(pipe.retriever, Retriever):
        raise SystemExit("record: the guide eval needs the real Retriever")
    dev = guide_eval(
        pipe,
        pipe.retriever,
        DATA / "eval" / "retrieval.json",
        DATA / "eval" / "incidents.json",
        "dev",
    )
    (DATA / "eval" / "report-dev.json").write_text(dev.model_dump_json(indent=2))
    FLOWS.write_text(json.dumps(got, indent=2, ensure_ascii=False))
    print(json.dumps(got, indent=2, ensure_ascii=False))
    blank = {
        k: ""
        for k in (
            "OPENAI_API_KEY",
            "TYPESAFE_API_KEY",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
        )
    }
    env = {**os.environ, **blank, "CRESSEY_MODEL_MODE": "replay"}
    check = subprocess.run(
        [sys.executable, "-m", "cressey.demo.record", "--check"], env=env, check=False
    )
    raise SystemExit(check.returncode)


def check() -> None:
    """The same plays with no model reachable: every answer must come from the cache."""
    s = Settings()
    if s.model_mode != "replay":
        raise SystemExit("record --check: run with CRESSEY_MODEL_MODE=replay")
    got = asyncio.run(plays(s))
    got.pop("_reports")
    recorded = json.loads(FLOWS.read_text())
    same = got == recorded
    print("offline replay:", "identical" if same else "DIFFERENT")
    if not same:
        print(
            json.dumps(
                {"recorded": recorded, "offline": got}, indent=2, ensure_ascii=False
            )
        )
    raise SystemExit(0 if same else 1)


if __name__ == "__main__":
    check() if "--check" in sys.argv else record("--fresh" in sys.argv)
