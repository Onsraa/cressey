"""A live Cressey server for tests: uvicorn in a thread, no model called."""

import asyncio
import socket
import sqlite3
import threading
import time
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path

import httpx2
import uvicorn

from cressey.app import create_app
from cressey.guide.models import Guide, GuideIncident
from cressey.settings import Settings


def fake_guide(gi: GuideIncident) -> Guide:
    """No model is called in these tests."""
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
def serving(demo: Path, hold_timeout: float) -> Generator[str]:
    settings = Settings(
        _env_file=None,
        openai_api_key=None,
        typesafe_api_key=None,
        demo_dir=demo,
        hold_timeout=hold_timeout,
    )
    app = create_app(settings, make_guide=fake_guide)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="warning", timeout_graceful_shutdown=1)
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    for _ in range(500):
        if server.started:
            break
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        server.should_exit = True
        thread.join(10)


async def api(base: str, method: str, path: str, **kw) -> httpx2.Response:
    async with httpx2.AsyncClient(base_url=base) as h:
        return await h.request(method, path, **kw)


async def next_hold(base: str) -> dict:
    for _ in range(250):
        holds = (await api(base, "GET", "/api/holds")).json()
        if holds:
            return holds[0]
        await asyncio.sleep(0.02)
    raise AssertionError("no hold appeared")


def users(demo: Path) -> int:
    with closing(sqlite3.connect(demo / "prod.sqlite")) as c:
        return c.execute("SELECT count(*) FROM users").fetchone()[0]
