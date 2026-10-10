import pytest

from cressey.core.floor import check, sql_risk
from cressey.core.models import Mandate, ToolRule

SQL = ToolRule(kind="sql", arg="query")
MAIL = ToolRule(kind="egress", arg="to")
NONE = Mandate()
TEAM = Mandate(may_send_to=["@example.test"])


@pytest.mark.parametrize(
    ("sql", "risk"),
    [
        ("SELECT * FROM users", "read"),
        ("INSERT INTO users VALUES (6, 'f@example.test')", "write"),
        # Rows changed in place can't be recovered, whatever the WHERE (stress test F1).
        ("UPDATE users SET name = 'x' WHERE id = 1", "destructive"),
        ("UPDATE users SET name = 'x' WHERE 1 = 1", "destructive"),
        ("UPDATE users SET name = 'x' WHERE true", "destructive"),
        ("UPDATE users SET name = 'x' WHERE email LIKE '%'", "destructive"),
        ("INSERT INTO t VALUES (1) ON CONFLICT(id) DO UPDATE SET a = 2", "destructive"),
        ("INSERT INTO t VALUES (1) ON CONFLICT DO NOTHING", "write"),
        ("INSERT OR IGNORE INTO users VALUES (1, 'a@example.test')", "write"),
        ("REPLACE INTO users VALUES (1, 'a@example.test')", "destructive"),
        ("INSERT OR REPLACE INTO users VALUES (1, 'a@example.test')", "destructive"),
        (
            "MERGE INTO users USING new ON users.id = new.id WHEN MATCHED THEN UPDATE SET email = new.email",
            "destructive",
        ),
        ("ALTER TABLE users RENAME TO old_users", "destructive"),
        ("ALTER TABLE users RENAME COLUMN email TO mail", "destructive"),
        ("REPLACE INTO t VALUES (1); DROP TABLE users", "destructive"),
        ("CREATE TABLE t (a INT)", "write"),
        ("ALTER TABLE users ADD COLUMN age INT", "write"),
        ("UPDATE users SET name = 'x'", "destructive"),
        ("DELETE FROM users WHERE id = 1", "destructive"),
        ("DROP TABLE IF EXISTS users", "destructive"),
        ("TRUNCATE TABLE users", "destructive"),
        ("ALTER TABLE users DROP COLUMN email", "destructive"),
        ("BEGIN; DELETE FROM users; ROLLBACK;", "destructive"),
        ("SELECT 1; /* cleanup */ DROP TABLE users", "destructive"),
        ("WITH d AS (DELETE FROM users RETURNING *) SELECT * FROM d", "destructive"),
        ("PRAGMA writable_schema = 1", "destructive"),
        ("vide la base", "destructive"),
        ("", "destructive"),
    ],
)
def test_sql_risk(sql, risk):
    assert sql_risk(sql)[0] == risk


def test_destructive_sql_outside_the_mandate_is_held():
    risk, reason = check(SQL, {"query": "DELETE FROM users"}, NONE)
    assert risk == "destructive" and reason is not None and "users" in reason


def test_destructive_sql_inside_the_mandate_passes():
    mandate = Mandate(may_destroy=["sessions"])
    query = {"query": "DELETE FROM sessions WHERE expired = 1"}
    assert check(SQL, query, mandate) == ("destructive", None)


def test_one_table_outside_the_mandate_holds_the_whole_query():
    mandate = Mandate(may_destroy=["sessions"])
    reason = check(SQL, {"query": "DELETE FROM sessions; DROP TABLE users"}, mandate)[1]
    assert reason is not None and "users" in reason


def test_sql_that_cant_be_classified_is_held_even_inside_the_mandate():
    mandate = Mandate(may_destroy=["users"])
    assert check(SQL, {"query": "PRAGMA writable_schema = 1"}, mandate)[1] is not None


def test_reads_and_writes_pass():
    assert check(ToolRule(kind="read"), {"path": "README.md"}, NONE) == ("read", None)
    assert check(SQL, {"query": "INSERT INTO users VALUES (6, 'x')"}, NONE) == (
        "write",
        None,
    )


def test_an_update_outside_the_mandate_is_held_whatever_its_where():
    risk, reason = check(SQL, {"query": "UPDATE users SET a = 1 WHERE 1 = 1"}, NONE)
    assert (risk, reason) == ("destructive", "SQL destructeur hors mandat : users")
    allowed = Mandate(may_destroy=["users"])
    assert check(SQL, {"query": "UPDATE users SET a = 1 WHERE id = 2"}, allowed) == (
        "destructive",
        None,
    )


READ = ToolRule(kind="read", arg="path")
WRITE = ToolRule(kind="write", arg="path")
GUARDED = Mandate(protected=["scorer", "runs/*/transcript.json", ".secrets/**"])


@pytest.mark.parametrize(
    "path",
    [
        "scorer",
        "scorer/score.py",
        "./scorer/score.py",
        "tests/../scorer/score.py",
        "Scorer/Score.py",
        "runs/42/transcript.json",
        ".secrets/db/key",
    ],
)
def test_a_protected_path_is_held_on_read_and_on_write(path):
    """The Hugging Face / METR read floor: no model is asked."""
    assert check(READ, {"path": path}, GUARDED) == ("read", f"chemin protégé : {path}")
    assert check(WRITE, {"path": path}, GUARDED)[1] == f"chemin protégé : {path}"


@pytest.mark.parametrize(
    "path", ["README.md", "scorer.md", "runs/42/notes.md", "src/scorer_test.py"]
)
def test_a_path_the_mandate_doesnt_protect_passes(path):
    assert check(READ, {"path": path}, GUARDED) == ("read", None)


def test_tool_missing_from_the_policy_is_held():
    risk, reason = check(None, {}, NONE)
    assert risk == "destructive" and reason is not None


def test_destructive_tool_is_always_held():
    mandate = Mandate(may_destroy=["users"])
    assert check(ToolRule(kind="destructive"), {}, mandate)[1] is not None


def test_email_inside_the_mandate_passes():
    assert check(MAIL, {"to": "dev@example.test"}, TEAM) == ("destructive", None)


@pytest.mark.parametrize(
    "to",
    [
        "x@evil.example",
        "x@evil-example.test",
        "dev@example.test.evil.example",
        ["dev@example.test", "x@evil.example"],
        42,
    ],
)
def test_email_outside_the_mandate_is_held(to):
    assert check(MAIL, {"to": to}, TEAM)[1] is not None
