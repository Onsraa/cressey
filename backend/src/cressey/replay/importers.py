"""What a recorded session is read from: the scripted sessions (data/sessions) and a Claude
Code transcript (the JSONL it writes as it works)."""

import json
from pathlib import Path

import yaml
from pydantic import JsonValue

from cressey.domain.runs import Mandate
from cressey.replay.trajectory import Call, Say, Session, Trajectory
from cressey.settings import DATA

SESSIONS = DATA / "sessions"


def load_sessions(folder: Path = SESSIONS) -> list[Session]:
    return [
        Session.model_validate(yaml.safe_load(p.read_text()))
        for p in sorted(folder.glob("*.yaml"))
    ]


def _text(content: JsonValue) -> str:
    """A tool result as text: a string, or its text blocks."""
    if isinstance(content, str):
        return content
    blocks = content if isinstance(content, list) else []
    return "\n".join(str(b.get("text", "")) for b in blocks if isinstance(b, dict))


def load_transcript(
    path: Path, task: str, mandate: Mandate | None = None
) -> Trajectory:
    """A Claude Code transcript: the agent's words, its calls and what each returned. Its
    report is the run's final result, else its last words. A transcript holds neither the
    task nor the mandate: they come with it."""
    steps: list[Say | Call] = []
    calls: dict[str, Call] = {}
    results: dict[str, tuple[str, bool]] = {}
    report = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:  # a line cut short, a line of logging
            continue
        kind = event.get("type")
        if kind == "result":
            report = event.get("result") or report
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            part = block.get("type")
            if kind == "assistant" and part == "text" and block.get("text", "").strip():
                steps.append(Say(say=block["text"].strip()))
            elif kind == "assistant" and part == "tool_use":
                call = Call(call=block.get("name", ""), args=block.get("input") or {})
                calls[block.get("id", "")] = call
                steps.append(call)
            elif kind == "user" and part == "tool_result":
                done = (_text(block.get("content")), bool(block.get("is_error")))
                results[block.get("tool_use_id", "")] = done
    for call_id, call in calls.items():
        if call_id in results:
            call.returned, call.failed = results[call_id]
    said = [s.say for s in steps if isinstance(s, Say)]
    return Trajectory(
        id=path.stem,
        task=task,
        mandate=mandate or Mandate(),
        steps=steps,
        report=report or (said[-1] if said else "(no final message)"),
    )
