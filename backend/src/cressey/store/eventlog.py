"""Append-only event log: each event carries the sha256 of the one before it, so an
edited or deleted record breaks the chain.

A truncated end leaves a chain that is still consistent, so head() exposes the last
hash and the count to anchor outside the log, and verify() checks a log against such
an anchor. With an anchor file, each append writes the head there, and the next start
checks the log against it. Not thread-safe: append from one thread (the event loop).
"""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, JsonValue, ValidationError


class Event(BaseModel):
    seq: int  # 0-based position
    ts: str  # UTC, ISO 8601
    kind: str  # "call", "hold", "decision"
    data: dict[str, JsonValue]
    prev: str  # hash of the previous event, "" for the first
    hash: str  # sha256 of the canonical JSON of every other field


def event_hash(event: Event) -> str:
    canonical = json.dumps(
        event.model_dump(exclude={"hash"}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class EventLog:
    def __init__(self, path: Path | None = None, anchor: Path | None = None) -> None:
        self.path, self.anchor = path, anchor
        self.events: list[Event] = []
        torn = path is not None and path.exists() and self._load(path)
        # Checked once, at start: appends then extend a chain they build themselves. A log
        # cut short or rewritten no longer matches the head the last process anchored, and a
        # log whose anchor is gone can't be vouched for.
        if anchor is None:
            self.intact = not torn and verify(self.events) is None
        else:
            head = _read_anchor(anchor)
            self.intact = (
                not torn
                and (head is not None or not self.events)
                and verify(self.events, head) is None
            )

    def _load(self, path: Path) -> bool:
        """The events in the file; True when its last line was cut short by a crash mid-write.
        That line is cut from the file, so the next event starts a line of its own; the event
        it held is lost. A line that doesn't read anywhere else is no crash: the start fails."""
        # Bytes, cut on "\n" only: str.splitlines() would also cut on the raw U+2028 and
        # U+0085 that JSON strings may hold.
        with path.open("rb") as f:
            lines = f.readlines()
        whole = 0  # bytes of the lines read
        for i, line in enumerate(lines):
            last = i == len(lines) - 1
            if last and not line.endswith(b"\n"):
                break
            try:
                self.events.append(Event.model_validate_json(line))
            except ValidationError:
                if not last:
                    raise
                break
            whole += len(line)
        else:
            return False
        with path.open("r+b") as f:
            f.truncate(whole)
        return True

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
        event.hash = event_hash(event)
        self.events.append(event)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        if self.anchor:
            _write_anchor(self.anchor, self.head())
        return event


def _read_anchor(path: Path) -> tuple[str, int] | None:
    if not path.exists():
        return None
    a = json.loads(path.read_text())
    return str(a["hash"]), int(a["count"])


def _write_anchor(path: Path, head: tuple[str, int]) -> None:
    """Replaced whole: a crash mid-write leaves the old head, never half of one."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"hash": head[0], "count": head[1]}))
    tmp.replace(path)


def verify(
    events: Sequence[Event], anchor: tuple[str, int] | None = None
) -> int | None:
    anchored_hash, count = anchor or ("", 0)
    prev = ""
    for i, event in enumerate(events):
        if event.seq != i or event.prev != prev or event.hash != event_hash(event):
            return i
        if i == count - 1 and event.hash != anchored_hash:
            return i
        prev = event.hash
    return len(events) if len(events) < count else None
