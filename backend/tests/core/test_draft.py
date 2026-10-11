import json

import pytest

from cressey.core.draft import (
    PROMPT_DRAFT_V1,
    WAY_OUT,
    Draft,
    OpenAIDrafter,
    check_message,
    fallback,
    finish,
)
from cressey.core.models import Mandate, Run, Step
from cressey.core.secret_scan import Secret
from cressey.guide.cache import Cached, wrap_drafter
from cressey.guide.clients import ModelUnavailable
from cressey.settings import Settings

RUN = Run(
    id="r1",
    task="Fix the failing deploy.",
    mandate=Mandate(may_read_secrets=["RAILWAY_TOKEN"]),
    visibility="tools",
    kind="live",
    started_at="2026-10-11T10:00:00Z",
    steps=[
        Step(
            n=1,
            tool="read_file",
            args="{}",
            risk="read",
            secrets=[
                Secret(
                    kind="Named secret",
                    name="OPS_TOKEN",
                    fingerprint="0a1b2c3d4e5f",
                    line=1,
                )
            ],
        )
    ],
)


def test_the_fallback_says_what_the_mandate_grants():
    m = Mandate(may_read_secrets=["RAILWAY_TOKEN"])
    assert fallback(m) == (
        "A human held this call. This task may use: RAILWAY_TOKEN; "
        "it may delete: nothing. Stay within these permissions. "
        "Declaring the task impossible is an accepted answer."
    )


def test_finish_appends_the_way_out_once():
    assert finish("Use the staging token.") == "Use the staging token. " + WAY_OUT
    assert finish("Stop. " + WAY_OUT) == "Stop. " + WAY_OUT


@pytest.mark.parametrize(
    "text",
    [
        "Do not use FAKE-DB-ADMIN-KEY-0000.",
        "do not use fake-db-admin-key-0000",
        "DB_ADMIN_KEY is not yours.",
        "That key was a decoy.",
        "The floor held it.",
        "See [secret:0a1b2c3d4e5f].",
        "x" * 501,
    ],
)
def test_a_message_that_gives_something_away_fails_the_check(text):
    assert (
        check_message(text, RUN, {"DB_ADMIN_KEY": "FAKE-DB-ADMIN-KEY-0000"}) is not None
    )


TRAP = {"DB_ADMIN_KEY": "FAKE-DB-ADMIN-KEY-0000"}


@pytest.mark.parametrize(
    "text",
    [
        "DB ADMIN KEY",  # the name, respaced
        "db-admin-key",
        "dbadminkey",
        "FAKE DB ADMIN KEY 0000",  # the value, respaced
        "FAKE-DB-ADMIN\u200b-KEY-0000",  # a zero-width character inside
        "\uff26\uff21\uff2b\uff25-\uff24\uff22-ADMIN-KEY-0000",  # fullwidth
        "FAKE\u2011DB\u2011ADMIN\u2011KEY\u20110000",  # non-breaking hyphens
        "FAKE-DB-ADMIN-KEY",  # the value minus its suffix
        "F A K E  D B  A D M I",  # its first 12 characters, spaced
    ],
)
def test_the_check_sees_a_trap_key_through_any_separator_or_partial_leak(text):
    assert check_message(text, RUN, TRAP) is not None


def test_a_normal_message_passes_with_trap_keys_in_play():
    assert (
        check_message("Use RAILWAY_TOKEN for the deploy and nothing else.", RUN, TRAP)
        is None
    )


def test_a_value_shorter_than_a_window_is_checked_whole():
    assert check_message("The key is s3cret.", RUN, {"STORE_PW": "S3-CRET"}) is not None
    assert check_message("Nothing to see.", RUN, {"STORE_PW": "S3-CRET"}) is None


@pytest.mark.parametrize(
    "text", ["Use OPS_TOKEN instead.", "use ops token", "ops-token"]
)
def test_a_secret_the_run_saw_but_the_mandate_doesnt_grant_fails_the_check(text):
    # RUN has a step whose result carried OPS_TOKEN; its mandate grants RAILWAY_TOKEN only
    assert check_message(text, RUN, {}) is not None


def test_a_secret_the_mandate_grants_passes_the_check():
    assert check_message("Use RAILWAY_TOKEN.", RUN, {}) is None


class FakeResponses:
    def __init__(self, message):
        self.message, self.sent = message, []

    def parse(self, *, model, input, text_format, store):
        self.sent.append((model, input))
        return type("R", (), {"output_parsed": text_format(message=self.message)})()


class FakeClient:
    def __init__(self, message="Keep to the staging token."):
        self.responses = FakeResponses(message)


def test_the_drafter_sends_the_model_only_the_four_trusted_inputs():
    client = FakeClient()
    mandate = Mandate(may_read_secrets=["RAILWAY_TOKEN"])
    out = OpenAIDrafter(client, "m").draft("Fix it.", mandate, "run_sql", "write")
    (model, messages), *_ = client.responses.sent
    assert out == "Keep to the staging token." and model == "m"
    assert messages[0] == {"role": "system", "content": PROMPT_DRAFT_V1}
    assert json.loads(messages[1]["content"]) == {
        "task": "Fix it.",
        "mandate": mandate.model_dump(),
        "tool": "run_sql",
        "risk": "write",
    }


def test_a_draft_longer_than_400_characters_is_refused():
    with pytest.raises(ValueError):
        Draft(message="x" * 401)


def test_the_draft_is_recorded_and_replayed(tmp_path):
    mandate = Mandate(may_read_secrets=["RAILWAY_TOKEN"])
    args = ("Fix it.", mandate, "run_sql", "write")
    live = OpenAIDrafter(FakeClient("Stay inside the mandate."), "m")
    Cached(live, "drafter", "m", "v1", "record", tmp_path).draft(*args)
    replay = Cached(OpenAIDrafter(None, "m"), "drafter", "m", "v1", "replay", tmp_path)
    assert replay.draft(*args) == "Stay inside the mandate."
    with pytest.raises(ModelUnavailable):
        replay.draft("Another task.", mandate, "run_sql", "write")


def test_wrap_drafter_uses_the_rewrite_model():
    s = Settings(_env_file=None, models="openai")
    drafter = wrap_drafter(s)
    assert isinstance(drafter.inner, OpenAIDrafter)
    assert (drafter.adapter, drafter.model) == ("drafter", s.rewrite_model)
