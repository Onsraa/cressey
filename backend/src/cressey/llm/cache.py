"""Record-and-replay for every model call, so the demo survives a network outage and replays
offline: one JSON file per call, named by a hash of what the model was asked. The judge, the
guides and the drafter share it.

live: call, store nothing · record: call and store, except a call already recorded,
which gets its first answer · replay: cache only, never the network
fallback: call; if the model is unavailable, serve the stored answer
replay-first: the stored answer when there is one, the network only on a miss (the stage)
"""

import hashlib
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from cressey.llm.clients import ModelUnavailable

log = logging.getLogger(__name__)

Mode = Literal["live", "record", "replay", "fallback", "replay-first"]


def cache_key(
    adapter: str, model: str, prompt_version: str, payload: dict[str, Any]
) -> str:
    blob = json.dumps(
        [adapter, model, prompt_version, payload], sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def prompt_version(prompt: str) -> str:
    """A prompt's version in a key: a changed prompt misses the cache."""
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]


class Cache:
    """The recorded answers of one model call site, in one folder."""

    def __init__(self, mode: Mode, folder: Path) -> None:
        self.mode, self.folder = mode, folder

    def file(
        self, adapter: str, model: str, version: str, payload: dict[str, Any]
    ) -> Path:
        return self.folder / f"{cache_key(adapter, model, version, payload)}.json"

    def first(self, file: Path) -> Any:
        """The stored answer when the mode serves it before any model is asked, else None.
        Record does too: a run and its Observer run ask the same, and a replay can give only
        one answer to both, so the recording keeps the first."""
        if self.mode in ("replay", "replay-first", "record") and file.exists():
            return json.loads(file.read_text())
        return None

    def fallback(self, file: Path) -> Any:
        """The stored answer for a model that didn't answer, in fallback mode, else None."""
        if self.mode == "fallback" and file.exists():
            return json.loads(file.read_text())
        return None

    def keep(self, file: Path, answer: Any) -> None:
        """A model's answer, stored when recording."""
        if self.mode == "record":
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps(answer, ensure_ascii=False))

    def call[T](
        self,
        adapter: str,
        model: str,
        version: str,
        payload: dict[str, Any],
        live: Callable[[], T],
        encode: Callable[[T], Any],
        decode: Callable[[Any], T],
    ) -> T:
        """A blocking client's call through the cache. Raises ModelUnavailable when neither
        the model nor the cache can answer."""
        file = self.file(adapter, model, version, payload)
        if (stored := self.first(file)) is not None:
            return decode(stored)
        if self.mode == "replay":
            raise ModelUnavailable(f"not in cache: {adapter}")
        if self.mode == "replay-first":
            log.warning("not recorded, asking live: %s", adapter)
        try:
            out = live()
        except ModelUnavailable:
            if (stored := self.fallback(file)) is not None:
                return decode(stored)
            raise
        self.keep(file, encode(out))
        return out
