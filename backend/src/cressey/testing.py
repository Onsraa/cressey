"""What the tests and the evals share: decision models that answer no or nothing, a guide
writer that calls no model, a live Cressey with its admin key, and a percentile."""

import asyncio
import sqlite3
from collections.abc import Generator, Mapping, Sequence
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Literal

import httpx2
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from typesafe_sdk import Choice

from cressey.app import create_app
from cressey.core.judge import Judge
from cressey.core.proxy import MCP_PATH
from cressey.demo.server import serve
from cressey.domain.guides import Guide, GuideIncident
from cressey.settings import Settings

# The control plane's key in every test app: conftest.py puts it in the environment too,
# for the tests that build their own Settings.
ADMIN = "test-admin"
ADMIN_AUTH = {"Authorization": f"Bearer {ADMIN}"}


def no_to_all(questions: Mapping) -> dict:
    """Every question answered no: 0 to a yes/no, « none » to a choice."""
    return {
        q: {"none": 1.0} if isinstance(v, Choice) else 0.0 for q, v in questions.items()
    }


class QuietJudge:
    """A decision model that answers no to everything, after `delay` seconds, and counts the
    calls it gets."""

    def __init__(self, delay: float = 0.0) -> None:
        self.delay, self.calls = delay, 0

    async def answers(self, state: dict, questions: Mapping) -> dict | None:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return no_to_all(questions)


class DownJudge:
    """Jev is down: no question gets an answer."""

    async def answers(self, state: dict, questions: Mapping) -> None:
        return None


def fake_guide(gi: GuideIncident) -> Guide:
    """A guide written with no model."""
    return Guide(
        id=f"g-{gi.id}",
        incident_id=gi.id,
        status="ok",
        message=None,
        steps=[],
        passages=[],
        dropped_steps=0,
    )


@contextmanager
def serving(
    demo: Path,
    hold_timeout: float,
    holds: Literal["wait", "refuse"] = "wait",
    judge: Judge | None = None,
    thought_holds: bool = False,
) -> Generator[str]:
    """A live Cressey on the demo tools in `demo`, no model called unless `judge` answers,
    its log in memory."""
    settings = Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        decider_url=None,
        demo_dir=demo,
        hold_timeout=hold_timeout,
        holds=holds,
        thought_holds=thought_holds,
        admin_token=ADMIN,
        state_dir=None,
    )
    with serve(create_app(settings, make_guide=fake_guide, judge=judge)) as base:
        yield base


async def api(base: str, method: str, path: str, **kw) -> httpx2.Response:
    """A call with the admin key, unless the caller passes its own Authorization (a run key)."""
    headers = {**ADMIN_AUTH, **kw.pop("headers", {})}
    async with httpx2.AsyncClient(base_url=base, timeout=30) as h:
        return await h.request(method, path, headers=headers, **kw)


def agent(base: str, key: str) -> Client:
    """An MCP client holding a run's key."""
    return Client(
        StreamableHttpTransport(
            base + MCP_PATH, headers={"Authorization": f"Bearer {key}"}
        )
    )


async def next_hold(base: str) -> dict:
    for _ in range(250):
        holds = (await api(base, "GET", "/api/holds")).json()
        if holds:
            return holds[0]
        await asyncio.sleep(0.02)
    raise AssertionError("no hold appeared")


def users(demo: Path) -> int:
    """The users left in the demo's production database."""
    with closing(sqlite3.connect(demo / "prod.sqlite")) as c:
        return c.execute("SELECT count(*) FROM users").fetchone()[0]


def percentile(values: Sequence[float], q: float) -> float:
    """The q-quantile (0 to 1) by nearest rank, handy for small samples; 0 for none."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]
