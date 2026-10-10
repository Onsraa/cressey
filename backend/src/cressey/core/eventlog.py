"""Append-only event log: each event carries the sha256 of the one before it, so an
edited or deleted record breaks the chain.

A truncated end leaves a chain that is still consistent, so head() exposes the last
hash and the count to anchor outside the log, and verify() checks a log against such
an anchor. Not thread-safe: append from one thread (the event loop).
"""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, JsonValue


class Event(BaseModel):
    seq: int  # 0-based position
    ts: str  # UTC, ISO 8601
    kind: str  # "call", "hold", "decision"
    data: dict[str, JsonValue]
    prev: str  # hash of the previous event, "" for the first
    hash: str  # sha256 of the canonical JSON of every other field


def _hash(event: Event) -> str:
    canonical = json.dumps(
        event.model_dump(exclude={"hash"}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class EventLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.events: list[Event] = []
        if path and path.exists():
            # Iterate the file: str.splitlines() would also cut on the raw U+2028 and
            # U+0085 that JSON strings may hold.
            with path.open(encoding="utf-8") as f:
                self.events = [Event.model_validate_json(line) for line in f]

    def head(self) -> tuple[str, int]:
        return (self.events[-1].hash if self.events else "", len(self.events))

    def append(self, kind: str, data: dict[str, JsonValue]) -> Event:
        event = Event(
            seq=len(self.events),
            ts=datetime.now(UTC).isoformat(),
            kind=kind,
            data=data,
            prev=self.head()[0],
            hash="",
        )
        event.hash = _hash(event)
        self.events.append(event)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        return event


def verify(
    events: Sequence[Event], anchor: tuple[str, int] | None = None
) -> int | None:
    anchored_hash, count = anchor or ("", 0)
    prev = ""
    for i, event in enumerate(events):
        if event.seq != i or event.prev != prev or event.hash != _hash(event):
            return i
        if i == count - 1 and event.hash != anchored_hash:
            return i
        prev = event.hash
    return len(events) if len(events) < count else None
