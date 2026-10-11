import pytest

from cressey.core.floor import check, shell_risk, sql_risk
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
    reason = check(SQL, {"query": "PRAGMA writable_schema = 1"}, mandate)[1]
    assert reason == "SQL Cressey can't classify"


def test_reads_and_writes_pass():
    assert check(ToolRule(kind="read"), {"path": "README.md"}, NONE) == ("read", None)
    assert check(SQL, {"query": "INSERT INTO users VALUES (6, 'x')"}, NONE) == (
        "write",
        None,
    )


def test_an_update_outside_the_mandate_is_held_whatever_its_where():
    risk, reason = check(SQL, {"query": "UPDATE users SET a = 1 WHERE 1 = 1"}, NONE)
    assert (risk, reason) == (
        "destructive",
        "destructive SQL outside the mandate: users",
    )
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
    assert check(READ, {"path": path}, GUARDED) == ("read", f"protected path: {path}")
    assert check(WRITE, {"path": path}, GUARDED)[1] == f"protected path: {path}"


@pytest.mark.parametrize(
    "path", ["README.md", "scorer.md", "runs/42/notes.md", "src/scorer_test.py"]
)
def test_a_path_the_mandate_doesnt_protect_passes(path):
    assert check(READ, {"path": path}, GUARDED) == ("read", None)


def test_tool_missing_from_the_policy_is_held():
    assert check(None, {}, NONE) == ("destructive", "tool not in the policy")


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


FROZEN = Mandate(frozen=["tests", "ci/grader.py"])


@pytest.mark.parametrize(
    "path", ["tests/test_app.py", "./tests/../tests/conftest.py", "CI/Grader.py"]
)
def test_a_frozen_path_reads_but_its_write_is_held(path):
    """ImpossibleBench: editing the tests was most of the cheating. No model is asked."""
    assert check(READ, {"path": path}, FROZEN) == ("read", None)
    assert check(WRITE, {"path": path}, FROZEN) == ("write", f"frozen path: {path}")


def test_a_path_outside_the_frozen_ones_is_written_freely():
    assert check(WRITE, {"path": "src/app.py"}, FROZEN) == ("write", None)


# GraphQL bodies: a query, a mutation, and an introspection query (mutationType is no mutation).
Q = '{"query":"query { project(id: \\"p1\\") { services { edges { node { id } } } } }"}'
M = '{"query":"mutation { serviceDelete(id: \\"s1\\") }"}'
I = '{"query":"{ __schema { mutationType { fields { name } } } }"}'
C = '{"query":"# volumes\\nquery { a }"}'  # a comment line, then the query
F = '{"query":"fragment F on V { id } query { ...F }"}'


@pytest.mark.parametrize(
    ("command", "risk"),
    [
        ("ls -la", "read"),
        ("cat .env.staging | grep TOKEN", "read"),
        ("git status && git diff", "read"),
        ("echo hi > notes.txt", "write"),
        (". ./.env.staging && curl -s https://api.test -d '{}'", "write"),
        ("rm -rf node_modules", "destructive"),
        ("psql -c 'DELETE FROM users'", "destructive"),
        ("git push --force origin main", "destructive"),
        # A curl or wget that only reads is a read; any body or method but a query's is a write.
        ("curl -s https://api.test/v2", "read"),
        ("curl -sI https://api.test", "read"),
        (
            f"curl -s -X POST https://api.test -H 'Content-Type: application/json' -d '{Q}'",
            "read",
        ),
        (f"curl -s https://api.test -d '{I}'", "read"),
        (
            f'OPS_TOKEN=abc curl -s "$API" -H "Authorization: Bearer $OPS_TOKEN" -d \'{Q}\'',
            "read",
        ),
        (
            f"API=https://api.test\n# Check volumes\ncurl -s \"$API\" \\\n  -H 'Content-Type: application/json' \\\n  -d '{Q}'",
            "read",
        ),
        ("export API=https://api.test", "read"),
        ("sleep 5 && curl -s https://api.test", "read"),
        ("wget -qO- https://api.test", "read"),
        (f"curl -s https://api.test -d '{M}'", "write"),
        ("curl -s -X DELETE https://api.test/v1/volumes/1", "write"),
        ("curl -s -X POST https://api.test", "write"),
        (f"curl -s -X PUT https://api.test -d '{Q}'", "write"),
        ("curl -s https://api.test -d @payload.json", "write"),
        ('curl -s https://api.test -d "$BODY"', "write"),
        ("curl -s https://api.test -F file=@a.txt", "write"),
        ("wget --post-data 'a=1' https://api.test", "write"),
        ("curl -s https://api.test | python3 -c 'import sys'", "write"),
        ("source .env.staging && curl -s https://api.test", "write"),
        # Short options can be glued to their value or to each other.
        ("curl -sXDELETE https://api.test", "write"),
        (f"curl -sd '{M}' https://api.test", "write"),
        (f"curl -s https://api.test -d '{Q}' -d '{M}'", "write"),
        ("curl -s --data-urlencode 'a=b' https://api.test", "write"),
        ("wget --post-data='a=1' https://api.test", "write"),
        ("curl -s 'https://api.test", "write"),
        ("API=$(curl -s -X POST https://api.test)", "write"),
        ('curl -s https://api.test -d "{\\"query\\":\\"`cat m.gql`\\"}"', "write"),
        (r"""curl -s https://api.test -d '{"query":"\u006dutation { a }"}'""", "write"),
        # Only a GraphQL query (a JSON string value) reads; other bodies with a "query" key don't.
        (
            'curl -s -X POST https://es.test/idx/_delete_by_query -d \'{"query":{"match_all":{}}}\'',
            "write",
        ),
        # A write can hide behind a first word that reads.
        (f"echo $(curl -s -X POST https://api.test -d '{M}')", "write"),
        (f"echo \"$(curl -s -X POST https://api.test -d '{M}')\"", "write"),
        (f"echo `curl -s -X POST https://api.test -d '{M}'`", "write"),
        ("cat <(curl -X DELETE https://api.test/v1/x)", "write"),
        ("sleep $(curl -X DELETE https://api.test/v1/x)", "write"),
        ("env curl -s -X DELETE https://api.test/v1/x", "write"),
        ("env", "read"),
        ("env | grep TOKEN", "read"),
        ("find . -name '*.tmp' -delete", "write"),
        ("find . -exec curl -s -X DELETE https://api.test {} +", "write"),
        ("find . -name x", "read"),
        # A single & backgrounds what precedes it and separates commands like ;, && and
        # redirections (2>&1) don't split.
        ("echo hi & curl -s -X DELETE https://api.test/v1/x", "write"),
        ("sleep 1 & curl -s -X DELETE https://api.test/v1/x", "write"),
        ("sleep 1 & curl -s https://api.test", "read"),
        ("ls 2>&1", "write"),
        # zsh's =(cmd) runs cmd like <(cmd) does.
        ("cat =(curl -s -X DELETE https://api.test/v1/x)", "write"),
        # A "query" nested in a non-GraphQL body (Elasticsearch) is no GraphQL query.
        (
            'curl -s -X POST https://es.test/idx/_delete_by_query -d \'{"query":{"match":{"title":{"query":"foo"}}}}\'',
            "write",
        ),
        ("curl -s https://api.test -d 'query=foo'", "write"),
        # A & inside quotes belongs to its argument, not to the shell.
        ('curl -s "https://x/?a=1&b=2"', "read"),
        ("curl -s 'https://x/?a=1&b=2'", "read"),
        ('curl -s https://api.test -H "X: a&b"', "read"),
        # ...but a quote the shell doesn't see (escaped, in a comment, $'..') hides nothing.
        ('echo \\" & curl -s -X DELETE https://api.test/v1/x #"', "write"),
        (
            "echo a # it's\necho hi & curl -s -X DELETE https://api.test/v1/x & echo 'b'",
            "write",
        ),
        (
            r"""echo $'it\'s' & curl -s -X DELETE https://api.test/v1/x & echo ' '""",
            "write",
        ),
        # A # starts a comment only at the start of a word: after a blank or ; & | ( ) < >.
        # Elsewhere (a NBSP or \r is no blank to the shell) it is part of a word.
        ("ls # it's fine & ok", "read"),
        (
            "echo hi;# '\necho x & curl -s -X DELETE https://api.test/v1/x & echo ''",
            "write",
        ),
        (
            "echo hi |# '\necho x & curl -s -X DELETE https://api.test/v1/x & echo ''",
            "write",
        ),
        ("echo a\u00a0# & curl -s -X DELETE https://api.test/v1/x", "write"),
        ("echo a\r# & curl -s -X DELETE https://api.test/v1/x", "write"),
        # A mutation is found in the query the server reads, not in the JSON text around it.
        (
            'curl -s https://api.test -d \'{"query":"query A { a }\\nmutation B { b }","operationName":"B"}\'',
            "write",
        ),
        (
            'curl -s https://api.test -d \'{"query":"query A { a }\\tmutation B { b }","operationName":"B"}\'',
            "write",
        ),
        # Only a GraphQL query document reads: SQL over HTTP, however it is wrapped, writes.
        (f"curl -s https://api.test -d '{C}'", "read"),
        (f"curl -s https://api.test -d '{F}'", "read"),
        (
            'curl -s -X POST https://db.test/query -d \'{"query":"UPDATE users SET plan = 1 WHERE id = 1"}\'',
            "write",
        ),
        (
            'curl -s -X POST https://db.test/query -d \'{"query":"INSERT INTO users (id) VALUES (1)"}\'',
            "write",
        ),
        (
            'curl -s -X POST https://db.test/query -d \'{"query":"SELECT * FROM users"}\'',
            "write",
        ),
        (
            'curl -s -X POST https://db.test/query -d \'{"query":"query_log"}\'',
            "write",
        ),
    ],
)
def test_shell_commands_are_classified(command, risk):
    assert shell_risk(command) == risk


def test_a_destructive_shell_command_is_held_whatever_the_mandate():
    shell = ToolRule(kind="shell", arg="command")
    assert check(shell, {"command": "rm -rf build"}, NONE) == (
        "destructive",
        "destructive shell command",
    )
    assert check(shell, {"command": "curl -s https://api.test -d @a.json"}, NONE) == (
        "write",
        None,
    )
