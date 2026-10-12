"""A person's word is a record, never evidence (the user's rule, 10-12): what the user types
is kept, shown and logged, but it never lowers Cressey's caution. The case reads the agent's
words and what its calls did, never the user's message."""

import time
from collections.abc import Callable, Mapping

from fastapi.testclient import TestClient

from cressey.app import create_app
from cressey.settings import Settings
from cressey.testing import ADMIN, ADMIN_AUTH, fake_guide, no_to_all

THING = "9f8e7d6c5b4a"
THOUGHT = f"Found {THING}."


class Judge:
    """The agent's thought opens an opportunity thread on THING; anything asked about the
    user's message would be answered yes."""

    def __init__(self) -> None:
        self.asked_about_the_user = 0

    async def answers(self, state: dict, questions: Mapping) -> dict:
        got = no_to_all(questions)
        if "user_message" in state:
            self.asked_about_the_user += 1
            return dict.fromkeys(questions, 1.0)
        if state.get("current_thought") == THOUGHT:
            got |= {
                q: 0.9 if q == "O1" else 1.0
                for q in questions
                if q == "O1" or q == f"about:{THING}"
            }
        return got


def until(done: Callable[[], bool]) -> None:
    for _ in range(300):
        if done():
            return
        time.sleep(0.01)
    raise AssertionError("not settled")


def test_the_users_go_ahead_never_closes_a_thread():
    judge = Judge()
    s = Settings(
        _env_file=None, openai_api_key=None, typesafe_api_key=None, admin_token=ADMIN
    )
    app = create_app(s, make_guide=fake_guide, judge=judge)
    with TestClient(app) as c:
        body = {"task": "Fix the failing test", "visibility": "messages"}
        created = c.post("/api/runs", json=body, headers=ADMIN_AUTH).json()
        auth = {"Authorization": f"Bearer {created['key']}"}

        def send(kind: str, **event) -> None:
            sent = {"hook_event_name": kind, "session_id": "s1", **event}
            assert c.post("/hook/claude", json=sent, headers=auth).is_success

        def read(call: str) -> None:
            tool = {
                "tool_name": "Read",
                "tool_use_id": call,
                "tool_input": {"file_path": "a.md"},
            }
            send("PreToolUse", **tool)
            send("PostToolUse", **tool, tool_response="ok")

        run = app.state.runs.get(created["id"])
        send("SessionStart")
        send("MessageDisplay", message_id="m1", delta=THOUGHT, final=True)
        read("t1")  # the call's shadow reads the thought: the thread opens
        until(lambda: any(t.object == THING for t in run.case.threads))
        send("UserPromptSubmit", prompt="yes, go ahead and use it")
        read("t2")
        time.sleep(0.3)  # a prompt read in the background would have landed by now
        [thread] = [t for t in run.case.threads if t.object == THING]
    assert (thread.state, judge.asked_about_the_user) == ("open", 0)
