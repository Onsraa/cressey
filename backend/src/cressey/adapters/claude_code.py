"""The agents' second way in: Claude Code's http hooks. The same decision as the MCP
proxy's, run on every tool call before it runs (PreToolUse) and once it has (PostToolUse,
PostToolUseFailure); the agent's reasoning streamed in live (MessageDisplay); the user's
prompts (UserPromptSubmit); the report taken when a turn ends (Stop); the session's start
and end (SessionStart, SessionEnd)."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import JsonValue

from cressey.adapters.auth import AuthorizationHeader, bearer
from cressey.domain.acts import Act, Agent
from cressey.domain.runs import Run, Step
from cressey.engine.agent_text import note
from cressey.engine.decide import Engine, Refused
from cressey.engine.report import report_check
from cressey.scan.trace import strings
from cressey.store.runs import Runs

router = APIRouter()
HOOK_PATH = "/hook/claude"
TOOL_EVENTS = ("PreToolUse", "PostToolUse", "PostToolUseFailure")


def _act(run: Run, event: dict[str, JsonValue]) -> Act:
    """The tool call a PreToolUse event announces. A subagent's call names it."""
    sub, sub_type = event.get("agent_id"), event.get("agent_type")
    agent = Agent(
        client="claude-code",
        model=run.agent.model,
        sub_agent=str(sub) if sub else None,
        sub_agent_type=str(sub_type) if sub_type else None,
    )
    args = event.get("tool_input")
    return Act(
        surface="hook",
        agent=agent,
        tool=str(event["tool_name"]),
        args=args if isinstance(args, dict) else {},
    )


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
    - UserPromptSubmit shows the user's prompt where it was sent, and unlocks the key: the
      person takes the run back, which says nothing about whether anything was safe. The
      prompt is a record, never read into the case (a person's word isn't evidence).
    - PreToolUse gets Cressey's decision: nothing when the call may run, a deny with the way
      out when it may not.
    - PostToolUse / PostToolUseFailure record what the call returned and read the step.
    - Stop takes the agent's last message as the report, checked against the log. It ends
      the turn; the run ends with the session (SessionEnd). A run with no session (a
      replay) has no other end: its Stop ends it.
    """
    runs: Runs = request.app.state.runs
    engine: Engine = request.app.state.engine
    # The calls being decided (None), then let through and not yet returned:
    # (run, tool_use_id) -> step.
    pending: dict[tuple[str, str], Step | None] = request.app.state.hook_calls
    run = runs.by_key(bearer(authorization))
    if run is None:
        raise HTTPException(403)
    event = await request.json()
    if session := event.get("session_id"):  # the replays send none
        run = runs.for_session(run, str(session))
    runs.route(run, "hook")
    kind = event["hook_event_name"]
    if kind == "SessionStart":
        runs.connect(run)
        if model := event.get("model"):  # omitted after /clear or a recovery restore
            runs.model(run, str(model), str(event.get("source", "")))
        return {}
    if kind == "PostModelSwitch":
        runs.model(run, str(event["to_model"]), str(event.get("source", "")))
        return {}
    if kind == "SessionEnd":
        # Killed mid-call: no result comes, for a call let through or still being decided.
        for call in [c for c in pending if c[0] == run.id]:
            if (step := pending.pop(call)) is not None:
                step.running = False
        runs.disconnect(run)
        engine.ended(run)
        return {}
    if kind == "UserPromptSubmit":
        runs.prompt(run, event.get("prompt") or "")
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
        # A run with no session (a replay) has no other end; a session's run ends with
        # its session (SessionEnd), even when its settings send no turns.
        final = run.session is None
        if final:
            runs.end(run, last)
        else:
            runs.answered(run, last)
        runs.checked(run, await report_check(run, engine.ledger, state.thresholds))
        if final:
            engine.ended(run)
        return {}
    if kind not in TOOL_EVENTS:  # an event Cressey doesn't follow
        return {}
    call = (run.id, str(event.get("tool_use_id", "")))
    if kind == "PreToolUse":
        pending[call] = None
        try:
            step = await engine.before(run, _act(run, event))
        except Refused as refused:
            pending.pop(call, None)
            return _deny(str(refused))
        if call in pending:
            pending[call] = step
        else:  # its session ended while it was decided: its result never comes
            step.running = False
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
