from cressey.adapters.broker import scoped
from cressey.demo.tools import PROD_KEY, READ_KEY
from cressey.domain.policy import Credential
from cressey.domain.runs import Mandate

DB = Credential(arg="key", read=READ_KEY, write=PROD_KEY)
SQL = {"query": "DELETE FROM users", "key": PROD_KEY}


def test_without_a_grant_the_tool_gets_the_read_credential_whatever_the_agent_sent():
    for sent in (PROD_KEY, "wrong", ""):
        args = scoped({**SQL, "key": sent}, DB, Mandate(), approved=False)
        assert args == {**SQL, "key": READ_KEY}


def test_a_mandate_that_grants_changes_gets_the_write_credential():
    args = scoped(SQL, DB, Mandate(may_destroy=["users"]), approved=False)
    assert args["key"] == PROD_KEY


def test_a_call_a_human_approved_gets_the_write_credential_once():
    assert scoped(SQL, DB, Mandate(), approved=True)["key"] == PROD_KEY


def test_a_tool_without_a_credential_is_left_alone():
    assert scoped(SQL, None, Mandate(), approved=False) is SQL
