"""Background tasks: one runs per key while it runs, and a new one may start once it ends."""

import asyncio

import pytest

from cressey.tasks import Tasks

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_a_key_runs_one_task_at_a_time():
    tasks: Tasks[str, int] = Tasks()
    gate, started = asyncio.Event(), []

    async def work(n: int) -> int:
        started.append(n)
        await gate.wait()
        return n

    first = tasks.once("k", lambda: work(1))
    assert tasks.once("k", lambda: work(2)) is first and tasks.get("k") is first
    gate.set()
    assert await first == 1 and started == [1]


async def test_a_key_is_free_again_once_its_task_ends():
    tasks: Tasks[str, int] = Tasks()

    async def work(n: int) -> int:
        return n

    assert await tasks.once("k", lambda: work(1)) == 1
    await asyncio.sleep(0)  # the done callback runs on the next turn of the loop
    assert tasks.get("k") is None
    assert await tasks.once("k", lambda: work(2)) == 2


async def test_a_task_without_a_key_runs_to_its_end():
    tasks: Tasks[str, None] = Tasks()
    ran = asyncio.Event()

    async def work() -> None:
        await asyncio.sleep(0)
        ran.set()

    task = tasks.spawn(work())
    await asyncio.wait_for(ran.wait(), 1)
    assert task.done()
