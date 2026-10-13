"""Work run off the request path. The event loop keeps only weak references to its tasks,
so these are held until they end; a task under a key (a run's id and a number) runs once at
a time for that key."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

Key = tuple[str, int]  # the run, and the step or message the task is about


class Tasks[T]:
    def __init__(self) -> None:
        self._running: set[asyncio.Task[T]] = set()
        self._keyed: dict[Key, asyncio.Task[T]] = {}

    def __len__(self) -> int:
        """How many are still running."""
        return len(self._running)

    def spawn(self, work: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        task = asyncio.get_running_loop().create_task(work)
        self._running.add(task)
        task.add_done_callback(self._running.discard)
        return task

    def get(self, key: Key) -> asyncio.Task[T] | None:
        """The task running under `key`, if any."""
        return self._keyed.get(key)

    def once(
        self, key: Key, start: Callable[[], Coroutine[Any, Any, T]]
    ) -> asyncio.Task[T]:
        """The task running under `key`, or a new one `start` begins."""
        task = self._keyed.get(key)
        if task is None:
            task = self._keyed[key] = self.spawn(start())
            task.add_done_callback(lambda _: self._keyed.pop(key, None))
        return task

    async def settled(self, run_id: str) -> None:
        """Every task keyed under this run has ended. What each returned or raised is left to
        whoever awaits it."""
        tasks = [task for (run, _), task in self._keyed.items() if run == run_id]
        if tasks:
            await asyncio.wait(tasks)
