"""Who asked for an act (the core design's I4), read from where its values came: the task,
the user's prompt, a tool's result the agent read, or else the agent itself."""

import time

from cressey.engine.provenance import asked_by
from tests.helpers import message, run_with, step

IBAN = "DE89370400440532013000"


def test_a_value_the_task_names_is_asked_by_the_task():
    run = run_with(task="Refund invoice INV-20261012 to the customer")
    assert asked_by(run, {"invoice": "INV-20261012"}) == ["task"]


def test_a_value_the_user_typed_is_asked_by_the_user():
    run = run_with(messages=[message(text=f"Pay {IBAN} today.", role="user")])
    assert asked_by(run, {"iban": IBAN}) == ["user"]


def test_a_value_read_in_a_result_is_asked_by_that_content():
    read = step(1, "read_file", result=f"New bank details: {IBAN}")
    assert asked_by(run_with(read), {"iban": IBAN}) == ["content"]


def test_the_agents_own_words_are_not_a_user_asking():
    run = run_with(messages=[message(text=f"I will pay {IBAN}.")])
    assert asked_by(run, {"iban": IBAN}) == ["agent"]


def test_an_act_with_no_value_from_elsewhere_is_the_agents_own():
    assert asked_by(run_with(), {"path": "README.md", "content": "x"}) == ["agent"]


def test_values_from_several_places_name_each_once():
    read = step(1, "read_file", result=f"Supplier IBAN: {IBAN}")
    run = run_with(read, task="Pay invoice INV-20261012")
    args = {"invoice": "INV-20261012", "iban": IBAN, "memo": "INV-20261012"}
    assert asked_by(run, args) == ["task", "content"]


def test_what_a_call_costs_doesnt_grow_with_what_the_run_read():
    """Each result is indexed once, so a call checks its own values only: the reviewer
    measured 15 s a call at 1,000 results of 10 KB before."""
    page = " ".join(f"row{i:06d}value" for i in range(600))  # about 10 KB of tokens
    run = run_with(
        *(step(n, "read_file", result=f"{n} {page}") for n in range(1, 1001))
    )
    args = {"content": " ".join(f"word{i:07d}x" for i in range(2_000))}  # 20 KB
    asked_by(run, args)  # the first call indexes what was read
    started = time.perf_counter()
    assert asked_by(run, args) == ["agent"]
    assert time.perf_counter() - started < 0.2
