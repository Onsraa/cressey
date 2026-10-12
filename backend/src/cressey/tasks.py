"""Work run off the request path. The event loop keeps only weak references to its tasks,
so these are held until they end; a task under a key runs once at a time for that key."""

import asyncio
from collections.abc import Callable, Coroutine, Hashable
from typing import Any


class Tasks[K: Hashable, T]:
    def __init__(self) -> None:
        self._running: set[asyncio.Task[T]] = set()
        self._keyed: dict[K, asyncio.Task[T]] = {}

    def spawn(self, work: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        task = asyncio.get_running_loop().create_task(work)
        self._running.add(task)
        task.add_done_callback(self._running.discard)
        return task

    def get(self, key: K) -> asyncio.Task[T] | None:
        """The task running under `key`, if any."""
        return self._keyed.get(key)

    def once(
        self, key: K, start: Callable[[], Coroutine[Any, Any, T]]
    ) -> asyncio.Task[T]:
        """The task running under `key`, or a new one `start` begins."""
        task = self._keyed.get(key)
        if task is None:
            task = self._keyed[key] = self.spawn(start())
            task.add_done_callback(lambda _: self._keyed.pop(key, None))
        return task
