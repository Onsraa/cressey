"""The agents' second way in: Claude Code's http hooks. The same decision as the MCP
proxy's, run on every tool call before it runs (PreToolUse) and once it has (PostToolUse,
PostToolUseFailure); the agent's reasoning streamed in live (MessageDisplay); the user's
prompts (UserPromptSubmit); the report taken when a turn ends (Stop); the session's start
and end (SessionStart, SessionEnd)."""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import JsonValue

from cressey.domain.runs import Step
from cressey.engine.agent_text import note
from cressey.engine.decide import Engine, Refused
from cressey.engine.report import report_check
from cressey.scan.trace import strings
from cressey.store.runs import Runs

router = APIRouter()
HOOK_PATH = "/hook/claude"
AuthorizationHeader = Annotated[str, Header()]


def _deny(reason: str) -> dict[str, JsonValue]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


@router.post(HOOK_PATH, include_in_schema=False)
async def claude_hook(
    request: Request, authorization: AuthorizationHeader = ""
) -> dict[str, JsonValue]:
    """One hook event, with the run's own key.

    - Each Claude Code session on the key gets its own run: /clear starts a new session.
    - MessageDisplay streams a slice of the agent's reasoning; it grows one message live, so
      the dashboard shows it as it is produced and the next call's judgment reads it. The
      decision model flags the message once it is final.
    - UserPromptSubmit shows the user's prompt where it was sent, and unlocks the key. The
      case reads it in the background: what it approves, what it answers.
    - PreToolUse gets Cressey's decision: nothing when the call may run, a deny with the way
      out when it may not.
    - PostToolUse / PostToolUseFailure record what the call returned and read the step.
    - Stop takes the agent's last message as the report, checked against the log. It ends
      the turn; the run ends with the session (SessionEnd). A run that never saw its
      session start (a replay, older settings) has no other end: its Stop ends it.
    """
    runs: Runs = request.app.state.runs
    engine: Engine = request.app.state.engine
    # The calls let through and not yet returned: (run, tool_use_id) -> step.
    pending: dict[tuple[str, str], Step] = request.app.state.hook_calls
    run = runs.by_key(authorization.removeprefix("Bearer ").strip())
    if run is None:
        raise HTTPException(403)
    event = await request.json()
    if session := event.get("session_id"):  # the replays send none
        run = runs.for_session(run, str(session))
    runs.route(run, "hook")
    kind = event["hook_event_name"]
    if kind == "SessionStart":
        runs.connect(run)
        return {}
    if kind == "SessionEnd":
        runs.disconnect(run)
        return {}
    if kind == "UserPromptSubmit":
        prompt = runs.prompt(run, event.get("prompt") or "")
        engine.case.read_prompt_soon(run, prompt.text)
        return {}
    if kind == "MessageDisplay":
        runs.stream(
            run,
            str(event.get("message_id", "")),
            event.get("delta") or "",
            bool(event.get("final")),
        )
        return {}
    if kind == "Stop":
        state = request.app.state
        last = event.get("last_assistant_message") or "(no final message)"
        if run.turn is None:
            runs.end(run, last)
        else:
            runs.answered(run, last)
        runs.checked(run, await report_check(run, engine.ledger, state.thresholds))
        return {}
    name = event["tool_name"]
    call = (run.id, str(event.get("tool_use_id", "")))
    if kind == "PreToolUse":
        try:
            pending[call] = await engine.before(
                run, name, event.get("tool_input") or {}
            )
        except Refused as refused:
            return _deny(str(refused))
        return {}
    step = pending.pop(call, None)
    if step is None:  # a call Cressey refused: Claude Code never ran it
        return {}
    failed = kind == "PostToolUseFailure"
    text = (
        str(event.get("error", ""))
        if failed
        else "\n".join(strings(event.get("tool_response")))
    )
    # The step is read now: its reasoning streamed in before the call, its result is here.
    told = await engine.after(run, step, failed, text)
    if told is None:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": kind,
            "additionalContext": note(told),
        }
    }
