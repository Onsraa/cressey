import json

import pytest
from pydantic import ValidationError

from cressey.replay.importers import load_sessions, load_transcript
from cressey.replay.trajectory import Call, Say, Session


def test_the_shipped_sessions_load():
    sessions = {s.id: s for s in load_sessions()}
    assert sessions["demo-tests-impossibles"].expect == "held"
    assert sessions["normal-readme"].expect == "free"


def test_a_claude_code_transcript_becomes_a_trajectory(tmp_path):
    def assistant(*blocks: dict) -> dict:
        return {"type": "assistant", "message": {"content": list(blocks)}}

    def returned(call: str, content: object, is_error: bool = False) -> dict:
        result = {"type": "tool_result", "tool_use_id": call, "content": content}
        return {
            "type": "user",
            "message": {"content": [{**result, "is_error": is_error}]},
        }

    lines = [
        {"type": "system", "subtype": "init"},
        assistant({"type": "text", "text": "  I'll look at the build first.  "}),
        assistant(
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}
        ),
        returned("t1", "app.js"),
        assistant(
            {
                "type": "tool_use",
                "id": "t2",
                "name": "Read",
                "input": {"file_path": "x"},
            }
        ),
        returned("t2", [{"type": "text", "text": "no such file"}], is_error=True),
        {"type": "result", "result": "The build is clean."},
    ]
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\nnot json\n")
    t = load_transcript(path, "Clean the build")
    assert (t.id, t.task, t.report) == (
        "transcript",
        "Clean the build",
        "The build is clean.",
    )
    assert t.steps == [
        Say(say="I'll look at the build first."),
        Call(call="Bash", args={"command": "ls"}, returned="app.js"),
        Call(
            call="Read", args={"file_path": "x"}, returned="no such file", failed=True
        ),
    ]


def test_a_line_that_is_json_but_not_an_event_is_skipped(tmp_path):
    lines = [
        '"starting"',
        "42",
        "null",
        json.dumps({"type": "result", "result": "Done."}),
    ]
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(lines) + "\n")
    t = load_transcript(path, "Do it")
    assert (t.steps, t.report) == ([], "Done.")


def test_a_session_without_a_report_is_refused():
    session = {
        "id": "s",
        "expect": "free",
        "task": "t",
        "steps": [{"call": "run_tests"}],
        "report_if_blocked": "Stopped.",
    }
    with pytest.raises(ValidationError, match="report"):
        Session.model_validate(session)
