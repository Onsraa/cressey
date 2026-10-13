"""Background tasks: one runs per key while it runs, and a new one may start once it ends."""

import asyncio

import pytest

from cressey.tasks import Tasks

pytestmark = pytest.mark.anyio
KEY = ("r1", 1)


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_a_key_runs_one_task_at_a_time():
    tasks: Tasks[int] = Tasks()
    gate, started = asyncio.Event(), []

    async def work(n: int) -> int:
        started.append(n)
        await gate.wait()
        return n

    first = tasks.once(KEY, lambda: work(1))
    assert tasks.once(KEY, lambda: work(2)) is first and tasks.get(KEY) is first
    gate.set()
    assert await first == 1 and started == [1]


async def test_a_key_is_free_again_once_its_task_ends():
    tasks: Tasks[int] = Tasks()

    async def work(n: int) -> int:
        return n

    assert await tasks.once(KEY, lambda: work(1)) == 1
    await asyncio.sleep(0)  # the done callback runs on the next turn of the loop
    assert tasks.get(KEY) is None
    assert await tasks.once(KEY, lambda: work(2)) == 2


async def test_a_task_without_a_key_runs_to_its_end():
    tasks: Tasks[None] = Tasks()
    ran = asyncio.Event()

    async def work() -> None:
        await asyncio.sleep(0)
        ran.set()

    task = tasks.spawn(work())
    assert len(tasks) == 1
    await asyncio.wait_for(ran.wait(), 1)
    await asyncio.sleep(0)  # the done callback runs on the next turn of the loop
    assert task.done() and len(tasks) == 0


async def test_settled_waits_for_the_tasks_of_one_run_and_leaves_their_errors():
    tasks: Tasks[None] = Tasks()
    gate = asyncio.Event()

    async def fails() -> None:
        await gate.wait()
        raise ValueError("read failed")

    async def other() -> None:
        await asyncio.Event().wait()  # another run's task never ends

    mine = tasks.once(("r1", 1), fails)
    stuck = tasks.once(("r2", 1), other)
    settling = asyncio.create_task(tasks.settled("r1"))
    await asyncio.sleep(0)
    assert not settling.done()
    gate.set()
    await asyncio.wait_for(settling, 1)  # the other run's task isn't waited for
    with pytest.raises(ValueError, match="read failed"):
        await mine  # its error is still there for whoever awaits it
    stuck.cancel()
