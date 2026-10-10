import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from cressey.core.eventlog import Event, EventLog, _hash, verify


def _log(n: int, path: Path | None = None) -> EventLog:
    log = EventLog(path)
    for i in range(n):
        log.append("call", {"i": i})
    return log


def test_appended_events_link_by_prev():
    log = _log(4)
    assert [e.seq for e in log.events] == [0, 1, 2, 3]
    assert log.events[0].prev == ""
    assert all(b.prev == a.hash for a, b in zip(log.events, log.events[1:]))
    assert verify(log.events) is None


def test_edited_event_is_caught():
    events = list(_log(8).events)
    events[3] = events[3].model_copy(update={"data": {"i": 99}})
    assert verify(events) == 3


def test_deleted_event_is_caught():
    events = list(_log(8).events)
    del events[5]
    assert verify(events) == 5


@pytest.mark.parametrize(
    ("index", "update", "bad"),
    [
        (3, {"data": {"i": 99}}, 4),  # re-hashed edit: the next event's prev is stale
        (7, {"seq": 99}, 7),  # re-hashed last event in the wrong position
    ],
)
def test_rehashed_forgery_is_caught(index, update, bad):
    events = list(_log(8).events)
    forged = events[index].model_copy(update=update)
    forged.hash = _hash(forged)
    events[index] = forged
    assert verify(events) == bad


def test_truncation_is_invisible_without_an_anchor():
    assert verify(_log(8).events[:-2]) is None


def test_truncation_is_caught_with_an_anchor():
    log = _log(8)
    kept = log.events[:-2]
    assert verify(kept, log.head()) == len(kept)


def test_rewritten_history_is_caught_by_the_anchor():
    anchor = _log(5).head()
    other = EventLog()
    for i in range(8):
        other.append("decision", {"i": i})
    assert verify(other.events) is None  # self-consistent: only the anchor can tell
    assert verify(other.events, anchor) == 4


def test_anchor_of_an_empty_log_accepts_any_chain():
    assert verify(_log(3).events, ("", 0)) is None


def test_head_of_an_empty_log():
    assert EventLog().head() == ("", 0)


def test_ts_is_utc_iso_8601():
    ts = EventLog().append("call", {}).ts
    assert datetime.fromisoformat(ts).utcoffset() == timedelta(0)


def test_hash_is_the_sha256_of_the_canonical_json_of_the_other_fields():
    event = EventLog().append("call", {"é": [1, 2.5, None], "a": {"b": True}})
    body = {"seq": 0, "ts": event.ts, "kind": "call", "data": event.data, "prev": ""}
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert event.hash == hashlib.sha256(canonical.encode()).hexdigest()


def test_reopened_log_has_the_same_events_and_head(tmp_path):
    path = tmp_path / "events.jsonl"
    log = _log(5, path)
    reopened = EventLog(path)
    assert reopened.events == log.events
    assert reopened.head() == log.head()


def test_edited_file_line_is_caught_after_reopen(tmp_path):
    path = tmp_path / "events.jsonl"
    _log(6, path)
    lines = path.read_text(encoding="utf-8").splitlines()
    edited = Event.model_validate_json(lines[2]).model_copy(update={"data": {"i": 99}})
    lines[2] = edited.model_dump_json()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert verify(EventLog(path).events) == 2


def test_append_after_reopen_continues_the_chain(tmp_path):
    path = tmp_path / "events.jsonl"
    last_hash = _log(3, path).head()[0]
    event = EventLog(path).append("call", {"i": 3})
    assert (event.seq, event.prev) == (3, last_hash)
    assert verify(EventLog(path).events) is None


def test_reopen_survives_unicode_line_separators(tmp_path):
    path = tmp_path / "events.jsonl"
    log = EventLog(path)
    log.append("call", {"text": "é日本 \u0085"})
    assert EventLog(path).events == log.events
