"""Who asked for an act (the core design's I4), read from where its values came: the task,
the user's prompt, a tool's result the agent read, or else the agent itself."""

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
