"""Append-only event log: each event carries the sha256 of the one before it, so an
edited or deleted record breaks the chain.

A truncated end leaves a chain that is still consistent, so head() exposes the last
hash and the count to anchor outside the log, and verify() checks a log against such
an anchor. With an anchor file, each append writes the head there, and the next start
checks the log against it. Not thread-safe: append from one thread (the event loop).
"""

import hashlib
import json
from collections.abc import Callable, Sequence
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


def read_lines[T](path: Path, parse: Callable[[bytes], T]) -> tuple[list[T], bool]:
    """Each line of an append-only file, parsed, and True when its last line was cut short
    by a crash mid-write: a line that doesn't parse is cut from the file, so the next write
    starts a line of its own; one that parses but lost its newline gets it back. A line
    that doesn't parse anywhere else is no crash: it raises."""
    # Bytes, cut on "\n" only: str.splitlines() would also cut on the raw U+2028 and U+0085
    # that JSON strings may hold.
    with path.open("rb") as f:
        lines = f.readlines()
    read: list[T] = []
    whole = 0  # bytes of the lines read
    for i, line in enumerate(lines):
        last = i == len(lines) - 1
        try:
            read.append(parse(line))
        except ValueError:  # JSON or pydantic: what a cut line raises
            if not last:
                raise
            break
        whole += len(line)
        if last and not line.endswith(b"\n"):
            # Cut between the record and its newline: the record is whole, finish the line.
            with path.open("ab") as f:
                f.write(b"\n")
    else:
        return read, False
    with path.open("r+b") as f:
        f.truncate(whole)
    return read, True


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
        """The events in the file; True when its last line was cut by a crash mid-write and
        the event it held is lost."""
        self.events, torn = read_lines(path, Event.model_validate_json)
        return torn

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
        if self.path:
            with self.path.open("ab") as f:
                end = f.tell()
                try:
                    f.write((event.model_dump_json() + "\n").encode())
                except (
                    OSError
                ):  # a full disk: no partial line for the next event to follow
                    f.truncate(end)
                    raise
        self.events.append(event)  # once on disk: a failed write leaves no event behind
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
