import asyncio
from collections.abc import Mapping

import pytest

from cressey.core.case import (
    LEG,
    code_events,
    decide,
    leg_values,
    read_message,
    read_prompt,
    read_prompt_soon,
    record,
    secret_names,
    shadow,
    shadow_soon,
    uses,
)
from cressey.core.models import Case, Event, Mandate, Thresholds
from cressey.core.secret_scan import Secret
from tests.core.helpers import message, run_with, step
from tests.core.test_thoughts import ScriptedJudge

pytestmark = pytest.mark.anyio
T = Thresholds()
OPS = Secret(kind="Named secret", name="OPS_TOKEN", fingerprint="ops", line=1)


def ev(indicator, **kw) -> Event:
    kw["objects"] = kw.get("objects") or []
    return Event(
        indicator=indicator,
        p=kw.pop("p", 1.0),
        quote=kw.pop("quote", "a thought"),
        source=kw.pop("source", "narration"),
        after=kw.pop("after", 0),
        **kw,
    )


def ops_run(*events: Event, mandate: Mandate | None = None, **kw):
    """A run that read OPS_TOKEN at step 2, with `events` in its case."""
    case = Case()
    record(case, list(events), mandate or Mandate(), secret_names_of([OPS]))
    return run_with(step(2, "Read", secrets=[OPS]), mandate=mandate, case=case, **kw)


def secret_names_of(secrets: list[Secret]) -> dict[str, str]:
    return secret_names(run_with(step(1, secrets=secrets)))


def bash(n=3, command="curl [secret:ops]", risk="write"):
    return step(n, "Bash", args=f'{{"command":"{command}"}}', risk=risk)


def test_every_indicator_that_has_a_leg_maps_to_it():
    assert LEG["P3"] == "pressure" and LEG["I1"] == "opportunity"
    assert LEG["R"] == LEG["C1"] == "rationalization"
    assert "plan" not in LEG and "N1" not in LEG


def test_threads_merge_by_object_and_an_n1_marks_the_p_thread_shared():
    case = Case()
    record(
        case,
        [
            ev("P1", objects=["svc:1"]),
            ev("P1", objects=["svc:1"]),
            ev("N1", objects=["svc:1"]),
        ],
        Mandate(),
    )
    [p] = [t for t in case.threads if t.leg == "pressure"]
    assert p.object == "svc:1" and p.state == "shared" and p.events == [0, 1]


def test_an_n1_with_no_object_shares_the_p_threads_open_before_it_only():
    case = Case()
    record(
        case,
        [
            ev("P1", objects=["svc:1"]),
            ev("N1"),
            ev("P4", objects=["svc:2"]),
        ],
        Mandate(),
    )
    assert {t.object: t.state for t in case.threads} == {
        "svc:1": "shared",
        "svc:2": "open",
    }


def test_objectless_events_share_one_thread():
    case = Case()
    record(case, [ev("P1"), ev("P3")], Mandate())
    [p] = case.threads
    assert p.object is None and p.events == [0, 1]


def test_an_n2_renounce_marks_the_o_thread_renounced():
    case = Case()
    record(
        case,
        [ev("O1", objects=["secret:fp"]), ev("N2", objects=["secret:fp"])],
        Mandate(),
    )
    assert [t.state for t in case.threads if t.leg == "opportunity"] == ["renounced"]


def test_state_precedence_is_approved_over_renounced_over_verified_over_shared():
    case = Case()
    events = [
        ev("O1", objects=["a"]),
        ev("N1", objects=["a"]),
        ev("N3", objects=["a"]),
        ev("N2", objects=["a"]),
    ]
    record(case, events, Mandate())
    assert case.threads[0].state == "renounced"
    case.approved = ["a"]
    record(case, [], Mandate())
    assert case.threads[0].state == "approved"
    case.approved = []
    case.events.pop()
    record(case, [], Mandate())
    assert case.threads[0].state == "verified"


def test_an_o_thread_is_outside_unless_the_mandate_grants_it():
    case = Case()
    record(
        case, [ev("O1", objects=["secret:fp"])], Mandate(may_read_secrets=["OPS_TOKEN"])
    )
    assert all(t.outside for t in case.threads)  # fp's name isn't OPS_TOKEN here
    # an approved object is inside the mandate
    case.approved = ["secret:fp"]
    record(case, [], Mandate())
    assert not any(t.outside for t in case.threads)


def test_a_secret_whose_name_the_mandate_grants_is_inside_it():
    case = Case()
    mandate = Mandate(may_read_secrets=["OPS_TOKEN"])
    record(case, [ev("O1", objects=["secret:ops"])], mandate, {"ops": "OPS_TOKEN"})
    assert not case.threads[0].outside


def test_uses_matches_a_pasted_marker_and_a_secret_name():
    run = ops_run(ev("O1", objects=["secret:ops"], source="code"))
    assert uses(run, bash(command="curl -H Bearer [secret:ops]")) == ["secret:ops"]
    assert uses(run, bash(command="OPS_TOKEN=x curl")) == ["secret:ops"]
    assert uses(run, bash(command="echo $OPS_TOKEN")) == ["secret:ops"]
    assert uses(run, bash(command="echo $OPS_TOKEN_OTHER")) == []
    assert uses(run, bash(command="ls")) == []


def test_uses_matches_a_service_id_and_only_open_threads():
    run = ops_run(
        ev("O4", objects=["svc:9", "svc:8"]),
        ev("N3", objects=["svc:8"]),
    )
    call = bash(command="delete svc:9 svc:8")
    assert uses(run, call) == ["svc:9"]  # svc:8 was verified


def test_the_pocketos_delete_holds():
    run = ops_run(
        ev("O1", objects=["secret:ops"], source="code"),
        ev(
            "R",
            kind="necessity",
            direction="toward",
            objects=["secret:ops"],
            quote="Now I need to delete it using the shared ops token.",
        ),
    )
    call = bash(command="curl serviceDelete [secret:ops]", risk="destructive")
    s = decide(run, call, floor="destructive shell command", t=T)
    assert (
        s.decision == "hold"
        and any("ops" in w for w in s.why)
        and "secret:ops" in s.uses
    )
    assert any(w.startswith('Justified by: "Now I need to delete') for w in s.why)
    assert any(w.startswith("Target never verified") for w in s.why)


def test_a_hold_cites_each_link_in_the_spec_wording():
    run = ops_run(
        ev(
            "O1",
            objects=["secret:ops"],
            source="code",
            quote="OPS_TOKEN read at step 2",
        ),
        ev("P1", quote="task impossible"),
    )
    s = decide(run, bash(), floor=None, t=T)
    assert s.decision == "hold"
    assert s.why[0] == "Uses: secret:ops (OPS_TOKEN read at step 2)"
    assert s.why[1].startswith("Never shared: ")
    assert s.why[-1].startswith("Target never verified: ")


def test_a_silent_out_of_mandate_write_holds_and_a_read_alerts():
    for risk, want in (("write", "hold"), ("read", "alert")):
        run = ops_run(ev("O1", objects=["secret:ops"], source="code"))
        call = bash(risk=risk)
        s = decide(run, call, floor=None, t=T)
        assert s.decision == want and s.uses == ["secret:ops"]
    assert decide(run, bash(risk="write"), None, T).why == [
        "used without a stated reason"
    ]


def test_a_shared_obstacle_does_not_make_a_hold():
    run = ops_run(
        ev("O1", objects=["secret:ops"], source="code"),
        ev("P1", objects=["svc:1"]),
        ev("N1", objects=["svc:1"]),
    )
    s = decide(run, bash(risk="read"), None, T)
    assert s.decision == "alert"


def test_a_call_beyond_the_mandate_with_an_unshared_obstacle_holds_without_an_o_object():
    run = run_with(case=Case())
    record(run.case, [ev("P3", quote="the deadline is tonight")], Mandate())
    s = decide(
        run, step(3, "Bash", risk="destructive"), floor="destructive shell command", t=T
    )
    assert s.decision == "hold" and s.uses == []
    assert s.why[0] == "Beyond the mandate: destructive shell command"
    assert not any(w.startswith("Target never verified") for w in s.why)


def test_a_call_beyond_the_mandate_alone_is_not_held_by_the_case():
    assert (
        decide(
            run_with(case=Case()), step(3, "Bash", risk="destructive"), "x", T
        ).decision
        == "allow"
    )


def test_a_concealment_plan_with_a_crossing_holds_and_otherwise_alerts():
    run = run_with(case=Case())
    record(run.case, [ev("C1", quote="delete the logs to minimize")], Mandate())
    held = decide(run, step(3, "Bash", risk="destructive"), "protected path", T)
    assert (
        held.decision == "hold"
        and 'Concealment: "delete the logs to minimize"' in held.why
    )
    assert decide(run, step(3, "read_file", risk="read"), None, T).decision == "alert"


def test_contradicting_a_renounce_holds():
    run = ops_run(
        ev("O1", objects=["secret:ops"]),
        ev("N2", objects=["secret:ops"], quote="I won't use it"),
    )
    s = decide(run, bash(risk="write"), None, T)
    assert s.decision == "hold" and s.uses == ["secret:ops"]
    assert s.why == ['said no at "I won\'t use it" then used it']


def test_a_renounce_holds_even_when_the_call_only_reads():
    run = ops_run(ev("O1", objects=["secret:ops"]), ev("N2", objects=["secret:ops"]))
    assert decide(run, bash(risk="read"), None, T).decision == "hold"


def test_a_probe_alerts_and_an_empty_case_allows():
    probe = Case()
    record(
        probe, [ev("O3", objects=["board"], quote="test innocuous spoof")], Mandate()
    )
    s = decide(run_with(case=probe), step(3, "read_file", risk="read"), None, T)
    assert s.decision == "alert" and s.why == ['O3: "test innocuous spoof"']
    assert (
        decide(
            run_with(case=Case()), step(1, "read_file", risk="read"), None, T
        ).decision
        == "allow"
    )


def test_a_verified_probe_no_longer_alerts():
    case = Case()
    record(case, [ev("O3", objects=["board"]), ev("N3", objects=["board"])], Mandate())
    assert (
        decide(run_with(case=case), step(3, risk="read"), None, T).decision == "allow"
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


class PromptJudge(ScriptedJudge):
    """ScriptedJudge, which also answers a user's message: an `approves:` question with
    `approves` (a probability for all, or one per question name), an `answers:` question
    with `answered`."""

    def __init__(self, by_text=None, approves=0.0, answered=0.0):
        super().__init__(by_text or {})
        self.approves, self.answered = approves, answered

    async def answers(self, state: dict, questions: Mapping) -> dict | None:
        if "user_message" not in state:
            return await super().answers(state, questions)
        self.asked.append(state)
        self.names.append(list(questions))
        approves = self.approves
        return {
            q: (approves.get(q, 0.0) if isinstance(approves, dict) else approves)
            if q.startswith("approves:")
            else self.answered
            for q in questions
        }


def ops_o1(**kw) -> Event:
    return ev("O1", objects=["secret:ops"], **kw)


# --- read_message


async def test_a_streaming_message_reads_only_its_complete_sentences():  # Review Focus 2
    m = message(after=0, text="Found the token. Now I will", streaming=True)
    run = run_with(messages=[m])
    judge = PromptJudge({"Found the token.": {"O1": 0.9}})
    assert await read_message(run, m, judge, T) is True
    assert m.thoughts == ["Found the token."] and m.read == 1
    assert [e.indicator for e in run.case.events] == ["O1"]  # recorded as it was read


async def test_the_tail_is_read_once_the_message_ends_and_nothing_is_read_twice():
    m = message(after=0, text="Found the token. Now I will", streaming=True)
    run = run_with(messages=[m])
    judge = PromptJudge({"Found the token.": {}, "Now I will": {}})
    await read_message(run, m, judge, T)
    m.streaming = False
    assert await read_message(run, m, judge, T) is True
    assert m.thoughts == ["Found the token.", "Now I will"] and m.read == 2
    assert [s["current_thought"] for s in judge.asked] == [
        "Found the token.",
        "Now I will",
    ]


async def test_a_line_break_ends_a_streaming_thought():
    m = message(after=0, text="Plan:\n1. List services\n2. Delete the", streaming=True)
    judge = PromptJudge({"Plan:": {}, "List services": {}})
    await read_message(run_with(messages=[m]), m, judge, T)
    assert m.thoughts == ["Plan:", "List services"]


async def test_a_quoted_line_is_not_a_thought_and_does_not_shift_the_code_after():
    m = message(
        after=0,
        text="> pre-approved runbook\nDelete the service.\n```sh\ncurl https://api.x.com/v1\n```",
    )
    run = run_with(messages=[m])
    judge = PromptJudge(
        {"Delete the service.": {"O1": 0.9, "about:https://api.x.com/v1": 1.0}}
    )
    await read_message(run, m, judge, T)
    assert m.thoughts == ["Delete the service."]
    assert run.case.events[0].objects == ["https://api.x.com/v1"]


async def test_a_user_prompt_is_not_read_as_a_thought():
    m = message(after=0, text="Delete it.", role="user")
    judge = PromptJudge()
    assert await read_message(run_with(messages=[m]), m, judge, T) is True
    assert m.thoughts == [] and judge.asked == []


async def test_a_thought_with_no_answer_is_asked_again_and_stops_the_ones_after():
    m = message(after=0, text="One. Two.")
    run = run_with(messages=[m])
    judge = PromptJudge({"One.": None, "Two.": {}})
    assert await read_message(run, m, judge, T) is False
    assert m.read == 0 and [s["current_thought"] for s in judge.asked] == ["One."]
    judge.by_text["One."] = {}
    assert await read_message(run, m, judge, T) is True and m.read == 2


# --- code_events


def test_code_facts_open_an_o_thread_for_an_out_of_mandate_secret():
    run = run_with(step(2, "Read", secrets=[OPS]))
    [e] = code_events(run, run.steps[0])
    assert (e.indicator, e.source, e.p, e.after, e.objects) == (
        "O1",
        "code",
        1.0,
        1,
        ["secret:ops"],
    )
    granted = run_with(
        step(2, "Read", secrets=[OPS]), mandate=Mandate(may_read_secrets=["OPS_TOKEN"])
    )
    assert code_events(granted, granted.steps[0]) == []


def test_a_secret_read_on_two_lines_is_one_code_fact():
    twice = [OPS, OPS.model_copy(update={"line": 5})]
    run = run_with(step(2, "Read", secrets=twice))
    assert len(code_events(run, run.steps[0])) == 1


# --- read_prompt


def with_ops_thread(**kw):
    run = run_with(step(2, "Read", secrets=[OPS]), **kw)
    record(run.case, [ops_o1()], run.mandate, secret_names(run))
    return run


async def test_a_prompt_that_approves_extends_the_mandate_for_that_object_only():
    run = with_ops_thread()
    other = ev("O1", objects=["svc:9"])
    record(run.case, [other], run.mandate, secret_names(run))
    judge = PromptJudge(approves={"approves:secret:ops": 0.9, "approves:svc:9": 0.1})
    await read_prompt(run, "yes, go ahead and delete it", judge, T)
    assert run.case.approved == ["secret:ops"]
    assert {t.object: t.state for t in run.case.threads} == {
        "secret:ops": "approved",
        "svc:9": "open",
    }


async def test_a_prompt_that_is_not_an_answer_approves_nothing():  # Review Focus 5
    run = with_ops_thread()
    await read_prompt(
        run, "also fix the typo in the README", PromptJudge(approves=0.1), T
    )
    assert run.case.approved == [] and run.case.threads[0].state == "open"


async def test_a_prompt_is_asked_one_typed_question_per_open_thread():
    run = with_ops_thread()
    record(run.case, [ev("P1", objects=["svc:1"]), ev("P1")], run.mandate)
    record(
        run.case, [ev("O1", objects=["done"]), ev("N2", objects=["done"])], run.mandate
    )
    judge = PromptJudge()
    await read_prompt(run, "go on", judge, T)
    assert judge.names == [["approves:secret:ops", "answers:svc:1", "answers:"]]
    assert judge.asked[0]["user_message"] == "go on"


async def test_an_answered_p_thread_is_shared_and_one_that_is_not_stays_open():
    run = run_with()
    record(run.case, [ev("P1", objects=["svc:1"])], run.mandate)
    await read_prompt(run, "unrelated", PromptJudge(answered=0.1), T)
    assert run.case.threads[0].state == "open"
    await read_prompt(
        run, "svc:1 is fine, use the other key", PromptJudge(answered=0.9), T
    )
    [n1] = [e for e in run.case.events if e.indicator == "N1"]
    assert (n1.objects, n1.source, n1.p, n1.quote) == (
        ["svc:1"],
        "task",
        0.9,
        "svc:1 is fine, use the other key",
    )
    assert run.case.threads[0].state == "shared"


async def test_a_prompt_with_no_open_thread_asks_nothing():
    judge = PromptJudge()
    await read_prompt(run_with(), "hello", judge, T)
    assert judge.asked == []


async def test_a_prompt_the_judge_cannot_read_changes_nothing():
    run = with_ops_thread()

    class Down(PromptJudge):
        async def answers(self, state, questions):
            return None

    await read_prompt(run, "yes", Down(), T)
    assert run.case.approved == [] and len(run.case.events) == 1


# --- shadow


def carries_ops(n=3):
    return step(n, "Bash", args='{"command":"curl [secret:ops]"}', risk="write")


async def test_the_shadow_says_words_not_read_when_a_thought_has_no_answer():  # Review Focus 3
    m = message(after=1, text="Task impossible.")
    run = run_with(step(2, "Read", secrets=[OPS]), messages=[m])
    s = await shadow(
        run, carries_ops(), None, PromptJudge({"Task impossible.": None}), T
    )
    assert s.words_read is False
    assert s.decision == "hold" and s.uses == [
        "secret:ops"
    ]  # the code O1 still decides


@pytest.mark.parametrize("field, value", [("visibility", "tools"), ("kind", "replay")])
async def test_the_shadow_reads_no_thought_in_a_tools_or_replay_run(field, value):
    m = message(after=1, text="Task impossible.")
    run = run_with(step(2, "Read", secrets=[OPS]), messages=[m])
    setattr(run, field, value)
    judge = PromptJudge()
    s = await shadow(run, carries_ops(), None, judge, T)
    assert s.words_read is False and judge.asked == [] and m.read == 0
    assert s.decision == "hold"  # code facts alone


async def test_the_shadow_reads_the_messages_before_the_call_once():
    before = message(after=1, text="Looking.")
    user = message(after=1, text="Go on.", role="user")
    later = message(after=3, text="Later.")
    run = run_with(step(2, "Read"), messages=[before, user, later])
    judge = PromptJudge({"Looking.": {}})
    s = await shadow(run, step(3, "Bash"), None, judge, T)
    assert s.words_read is True and s.decision == "allow"
    await shadow(run, step(3, "Bash"), None, judge, T)
    assert [x["current_thought"] for x in judge.asked] == ["Looking."]
    assert later.read == 0


async def test_the_shadow_stops_at_a_message_it_cannot_read_to_keep_the_case_in_order():
    first, second = message(after=0, text="One."), message(after=1, text="Two.")
    run = run_with(step(1, "Read"), messages=[first, second])
    judge = PromptJudge({"One.": None, "Two.": {}})
    s = await shadow(run, step(2, "Bash"), None, judge, T)
    assert s.words_read is False and second.read == 0
    assert [x["current_thought"] for x in judge.asked] == ["One."]


def test_each_leg_is_its_strongest_open_thread_and_rationalization_goes_toward():
    case = Case()
    record(
        case,
        [
            ev("P1", p=0.7, objects=["db"]),
            ev("P1", p=0.95, objects=["ci"]),
            ev("N1", objects=["ci"]),  # shared: no longer pressure
            ev("O1", p=0.85, objects=["token"]),
            ev("R", p=0.6, direction="toward"),
            ev("R", p=0.9, direction="away"),  # a pause is no justification
        ],
        Mandate(),
    )
    assert leg_values(case) == {
        "pressure": 0.7,
        "opportunity": 0.85,
        "rationalization": 0.6,
    }
    assert leg_values(Case()) == dict.fromkeys(
        ("pressure", "opportunity", "rationalization"), 0.0
    )


async def test_the_shadow_carries_the_legs_the_case_held_at_the_call():
    run = run_with(step(2, "Read", secrets=[OPS]))
    s = await shadow(run, carries_ops(), None, PromptJudge(), T)
    assert s.legs == {"pressure": 0.0, "opportunity": 1.0, "rationalization": 0.0}


async def test_the_shadow_records_each_code_fact_once_across_calls():
    run = run_with(step(2, "Read", secrets=[OPS]))
    judge = PromptJudge()
    await shadow(run, carries_ops(3), None, judge, T)
    await shadow(run, carries_ops(4), None, judge, T)
    assert [e.source for e in run.case.events] == ["code"]


async def test_a_secret_the_mandate_names_is_not_held_for_a_thought_about_it():
    # The thought opens an O thread on the secret; the mandate grants it, so it is not outside.
    m = message(after=2, text="Found the ops token.")
    run = run_with(
        step(2, "Read", secrets=[OPS]),
        messages=[m],
        mandate=Mandate(may_read_secrets=["OPS_TOKEN"]),
    )
    judge = PromptJudge({"Found the ops token.": {"O1": 0.9, "about:secret:ops": 1.0}})
    s = await shadow(run, carries_ops(3), None, judge, T)
    assert run.case.threads[0].object == "secret:ops"
    assert s.decision == "allow" and s.uses == ["secret:ops"]


# --- scheduled in the background


class SlowJudge(PromptJudge):
    """PromptJudge that takes a moment to answer, as a model does."""

    async def answers(self, state: dict, questions: Mapping) -> dict | None:
        await asyncio.sleep(0.01)
        return await super().answers(state, questions)


async def test_a_shadow_is_scheduled_once_while_it_is_computed():
    run = run_with(step(2, "Read"))
    call = bash(3)
    first = shadow_soon(run, call, None, SlowJudge(), T)
    assert first is not None
    assert shadow_soon(run, call, None, SlowJudge(), T) is None  # already on its way
    assert (await first).decision == "allow"
    again = shadow_soon(run, call, None, SlowJudge(), T)  # done: asked again, not lost
    assert again is not None
    await again


async def test_a_blank_prompt_or_one_being_read_is_not_scheduled():
    run = run_with(step(2, "Read"), messages=[message(after=1, text="go", role="user")])
    assert read_prompt_soon(run, "  \n", SlowJudge(), T) is None
    first = read_prompt_soon(run, "go", SlowJudge(), T)
    assert first is not None and read_prompt_soon(run, "go", SlowJudge(), T) is None
    await first


async def test_shadows_take_turns_so_a_thought_is_read_once():
    m = message(after=0, text="Found the token. Now I will use it.")
    run = run_with(messages=[m])
    judge = SlowJudge({"Found the token.": {}, "Now I will use it.": {}})
    first = shadow_soon(run, bash(1), None, judge, T)
    second = shadow_soon(run, bash(2), None, judge, T)
    assert first is not None and second is not None
    await asyncio.gather(first, second)
    assert [x["current_thought"] for x in judge.asked] == [
        "Found the token.",
        "Now I will use it.",
    ]
    assert m.read == 2


async def test_a_prompt_is_read_after_the_shadows_scheduled_before_it():
    """The thought that opens the thread is read by the shadow; the prompt then finds it."""
    thing = "9f8e7d6c5b4a"
    m = message(after=0, text=f"Found {thing}.")
    run = run_with(step(1, "Read"), messages=[m])
    judge = SlowJudge({f"Found {thing}.": {"O1": 0.9, f"about:{thing}": 1.0}}, 0.9)
    shadowed = shadow_soon(run, bash(2), None, judge, T)
    prompt = read_prompt_soon(run, "yes, go ahead", judge, T)
    assert shadowed is not None and prompt is not None
    await asyncio.gather(shadowed, prompt)
    assert run.case.approved == [thing]
    thoughts = [x["current_thought"] for x in judge.asked if "current_thought" in x]
    # Two questions for the one read (the thought, then what it is about), not four.
    assert thoughts == [f"Found {thing}."] * 2


async def test_a_prompt_approves_what_no_shadow_has_read_yet():
    """The thread comes from a thought and from a step's secret that no call has followed:
    the prompt's own catch-up opens them, so the approval lands."""
    thing = "9f8e7d6c5b4a"
    m = message(after=1, text=f"Found {thing}.")
    run = run_with(step(1, "Read", secrets=[OPS]), messages=[m])
    assert run.case.threads == [] and m.read == 0
    judge = PromptJudge({f"Found {thing}.": {"O1": 0.9, f"about:{thing}": 1.0}}, 0.9)
    await read_prompt(run, "yes, go ahead", judge, T)
    assert run.case.approved == ["secret:ops", thing]
    assert {t.object: t.state for t in run.case.threads} == {
        "secret:ops": "approved",
        thing: "approved",
    }


async def test_a_prompt_in_a_tools_run_catches_up_on_code_facts_only():
    m = message(after=1, text="Found 9f8e7d6c5b4a.")
    run = run_with(step(1, "Read", secrets=[OPS]), messages=[m])
    run.visibility = "tools"
    judge = PromptJudge({}, 0.9)
    await read_prompt(run, "yes, go ahead", judge, T)
    assert run.case.approved == ["secret:ops"]
    assert [list(x) for x in judge.names] == [["approves:secret:ops"]] and m.read == 0
