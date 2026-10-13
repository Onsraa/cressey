import pytest

from cressey.domain.policy import ToolRule
from cressey.domain.reasons import Reason
from cressey.domain.runs import Mandate
from cressey.engine.floor.rules import check
from cressey.engine.floor.shell import inline_sql, shell_risk
from cressey.engine.floor.sql import sql_risk
from cressey.engine.floor.tripwires import at_cressey, origin

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


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM users WHERE a->1e9 = 1",
        "SELECT " + "(" * 5000 + "1" + ")" * 5000,
    ],
    ids=["a ValueError", "a RecursionError"],
)
def test_sql_that_makes_the_parser_raise_cant_be_classified(sql):
    assert sql_risk(sql) == ("destructive", None)


def test_destructive_sql_outside_the_mandate_is_held():
    risk, reason = check(SQL, {"query": "DELETE FROM users"}, NONE)
    assert (risk, reason) == (
        "destructive",
        Reason(check="destructive_sql", target="users"),
    )


def test_destructive_sql_inside_the_mandate_passes():
    mandate = Mandate(may_destroy=["sessions"])
    query = {"query": "DELETE FROM sessions WHERE expired = 1"}
    assert check(SQL, query, mandate) == ("destructive", None)


def test_one_table_outside_the_mandate_holds_the_whole_query():
    mandate = Mandate(may_destroy=["sessions"])
    reason = check(SQL, {"query": "DELETE FROM sessions; DROP TABLE users"}, mandate)[1]
    assert reason == Reason(check="destructive_sql", target="users")


def test_sql_that_cant_be_classified_is_held_even_inside_the_mandate():
    mandate = Mandate(may_destroy=["users"])
    reason = check(SQL, {"query": "PRAGMA writable_schema = 1"}, mandate)[1]
    assert reason == Reason(check="unclassified_sql")


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
        Reason(check="destructive_sql", target="users"),
    )
    allowed = Mandate(may_destroy=["users"])
    assert check(SQL, {"query": "UPDATE users SET a = 1 WHERE id = 2"}, allowed) == (
        "destructive",
        None,
    )


READ = ToolRule(kind="read", arg="path")
EDIT = ToolRule(kind="edit", arg="path")
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
def test_a_protected_path_is_held_on_read_and_on_edit(path):
    """The Hugging Face / METR read floor: no model is asked."""
    held = Reason(check="protected_path", target=path)
    assert check(READ, {"path": path}, GUARDED) == ("read", held)
    assert check(EDIT, {"path": path}, GUARDED)[1] == held


@pytest.mark.parametrize(
    "path", ["README.md", "scorer.md", "runs/42/notes.md", "src/scorer_test.py"]
)
def test_a_path_the_mandate_doesnt_protect_passes(path):
    assert check(READ, {"path": path}, GUARDED) == ("read", None)


def test_tool_missing_from_the_policy_is_held():
    assert check(None, {}, NONE) == ("destructive", Reason(check="unknown_tool"))


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
def test_a_frozen_path_reads_but_its_edit_is_held(path):
    """ImpossibleBench: editing the tests was most of the cheating. No model is asked."""
    assert check(READ, {"path": path}, FROZEN) == ("read", None)
    held = Reason(check="frozen_path", target=path)
    assert check(EDIT, {"path": path}, FROZEN) == ("write", held)


def test_a_path_outside_the_frozen_ones_is_written_freely():
    assert check(EDIT, {"path": "src/app.py"}, FROZEN) == ("write", None)


def test_only_an_edits_argument_is_a_path():
    """A write names no argument, so nothing of it is checked against the protected and
    frozen paths: a user named after one is no file."""
    create_user = ToolRule(kind="write")
    assert check(create_user, {"name": "scorer"}, GUARDED) == ("write", None)
    assert check(create_user, {"name": "tests"}, FROZEN) == ("write", None)


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
        ("ls 2>&1", "read"),
        # zsh's =(cmd) runs cmd like <(cmd) does.
        ("cat =(curl -s -X DELETE https://api.test/v1/x)", "write"),
        # A request's method, body or target can come from elsewhere: a config file, an
        # expanded option, a second transfer, a command sent over FTP, a wget startup command.
        ("echo 'request = \"DELETE\"' | curl -K - https://api.test", "write"),
        ("curl -s --config req.cfg https://api.test", "write"),
        ("curl -sK req.cfg https://api.test", "write"),
        ("curl --expand-request DELETE https://api.test", "write"),
        ("curl --expand-data 'x=1' https://api.test", "write"),
        ("curl --form-string a=b https://api.test", "write"),
        (
            f"curl -d '{Q}' https://api.test/a --next -X POST https://api.test/b",
            "write",
        ),
        (f"curl -d '{Q}' https://api.test/a -: -X POST https://api.test/b", "write"),
        ("curl -Q 'DELE x' ftp://ftp.test", "write"),
        ("curl --quote 'DELE x' ftp://ftp.test", "write"),
        ("wget -e method=DELETE https://api.test", "write"),
        ("wget -qe method=DELETE -O- https://api.test", "write"),
        ("wget --execute method=DELETE -O- https://api.test", "write"),
        # curl -o/-O and a plain wget write a file; only stdout (or /dev/null) reads.
        ("curl -o ~/.zshrc https://api.test", "write"),
        ("curl -s --output x.sh https://api.test", "write"),
        ("curl -O https://api.test/x.sh", "write"),
        ("curl -sSLO https://api.test/x.sh", "write"),
        ("curl --remote-name https://api.test/x.sh", "write"),
        ("curl -s -o /dev/null -w '%{http_code}' https://api.test", "read"),
        ("curl -s -o - https://api.test", "read"),
        ("wget https://api.test", "write"),
        ("wget -O out.html https://api.test", "write"),
        ("wget -qO out.html https://api.test", "write"),
        ("wget -O - https://api.test", "read"),
        ("wget -O- https://api.test", "read"),
        ("wget --output-document=- https://api.test", "read"),
        ("wget --output-document - https://api.test", "read"),
        # Redirections to /dev/null and fd duplications write nothing; any other target does.
        ("curl -s https://api.test 2>/dev/null", "read"),
        ("curl -s https://api.test >/dev/null 2>&1", "read"),
        ("curl -s https://api.test &>/dev/null", "read"),
        ("curl -s https://api.test >> /dev/null", "read"),
        ("curl -s https://api.test 2>>/dev/null", "read"),
        ("echo hi >&2", "read"),
        ("curl -s https://api.test > out.json", "write"),
        ("curl -s https://api.test >out.json 2>/dev/null", "write"),
        ("echo hi >&out.txt", "write"),
        ("echo hi >/dev/nullx", "write"),
        ("echo hi >/dev/null/../tmp/x", "write"),
        ("curl -s -X POST https://api.test -H 'X: FAKE-KEY' 2>/dev/null", "write"),
        ("echo hi 2>&1 & curl -s -X DELETE https://api.test/v1/x", "write"),
        ("echo hi &>/dev/null & curl -s -X DELETE https://api.test/v1/x", "write"),
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
        # An escaped character is part of its word: a # after it is no comment (and the line
        # continuation joins the words, as in the shell).
        ("echo \\ # & curl -s -X DELETE https://api.test/v1/x", "write"),
        ("echo \\;# & curl -s -X DELETE https://api.test/v1/x", "write"),
        ("echo \\|# & curl -s -X DELETE https://api.test/v1/x", "write"),
        ("echo \\&# & curl -s -X DELETE https://api.test/v1/x", "write"),
        ("echo \\(# & curl -s -X DELETE https://api.test/v1/x", "write"),
        ("echo \\\t# & curl -s -X DELETE https://api.test/v1/x", "write"),
        ("echo a\\\n# & curl -s -X DELETE https://api.test/v1/x", "write"),
        # What can't be told: a here-document, an open quote, a trailing backslash.
        ("cat <<EOF\nx\nEOF", "write"),
        ("echo 'unterminated", "write"),
        ("echo trailing\\", "write"),
        # ; | & and ( ) inside quotes are text; outside they separate commands.
        ("echo 'a; b | c' && ls", "read"),
        ("(cd src && ls)", "read"),
        # A mutation is found in the query the server reads, not in the JSON text around it.
        (
            'curl -s https://api.test -d \'{"query":"query A { a }\\nmutation B { b }","operationName":"B"}\'',
            "write",
        ),
        (
            'curl -s https://api.test -d \'{"query":"query A { a }\\tmutation B { b }","operationName":"B"}\'',
            "write",
        ),
        # A body with the key twice is read by the server as it likes: the mutation may win.
        (
            'curl -s https://api.test -d \'{"query":"mutation B { b }","query":"query A { a }"}\'',
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
        Reason(check="destructive_shell"),
    )
    assert check(shell, {"command": "curl -s https://api.test -d @a.json"}, NONE) == (
        "write",
        None,
    )


@pytest.mark.parametrize(
    ("command", "sql"),
    [
        ('psql -h db -c "SELECT 1"', ["SELECT 1"]),
        ("psql --command 'SELECT 1'", ["SELECT 1"]),
        ("psql --command='SELECT 1'", ["SELECT 1"]),
        ('PGPASSWORD=x psql -c "SELECT 1"', ["SELECT 1"]),
        ('mysql -u root -e "SELECT 1"', ["SELECT 1"]),
        ("mysql --execute='SELECT 1'", ["SELECT 1"]),
        ('mariadb -e "SELECT 1"', ["SELECT 1"]),
        ("mariadb --execute 'SELECT 1'", ["SELECT 1"]),
        ('clickhouse-client -q "SELECT 1"', ["SELECT 1"]),
        ("clickhouse-client --query='SELECT 1'", ["SELECT 1"]),
        # sqlite3 and duckdb take the SQL after the database file; options come before it.
        ('sqlite3 app.db "SELECT 1"', ["SELECT 1"]),
        ('sqlite3 -header app.db "SELECT 1" "SELECT 2"', ["SELECT 1", "SELECT 2"]),
        ('duckdb app.duckdb "SELECT 1"', ["SELECT 1"]),
        # Each simple command, and each SQL a client is given.
        ('cd db && psql -c "SELECT 1"; mysql -e "SELECT 2"', ["SELECT 1", "SELECT 2"]),
        ('psql -c "SELECT 1" -c "SELECT 2"', ["SELECT 1", "SELECT 2"]),
        # Nothing to read: no SQL given inline, a flag without its SQL, another command, a
        # line the splitter can't tell (a here-document).
        ("sqlite3 app.db", []),
        ("psql -f script.sql", []),
        ("psql -c", []),
        ("ls -la", []),
        ("psql <<EOF\nSELECT 1;\nEOF", []),
    ],
)
def test_inline_sql_is_read_from_each_client(command, sql):
    assert inline_sql(command) == sql


@pytest.mark.parametrize(
    ("command", "mandate", "risk", "reason"),
    [
        (
            'psql -h prod -c "UPDATE accounts SET balance = 0"',
            NONE,
            "destructive",
            Reason(check="destructive_sql", target="accounts"),
        ),
        (
            'PGPASSWORD=x psql -c "UPDATE accounts SET balance = 0"',
            NONE,
            "destructive",
            Reason(check="destructive_sql", target="accounts"),
        ),
        # Inside the mandate the reason is the shell's own: none for an UPDATE, which the
        # destructive-command regex doesn't know...
        (
            'psql -c "UPDATE accounts SET balance = 0"',
            Mandate(may_destroy=["accounts"]),
            "destructive",
            None,
        ),
        (
            'psql -c "DELETE FROM users"',
            NONE,
            "destructive",
            Reason(check="destructive_sql", target="users"),
        ),
        # ...and destructive_shell for a DELETE, which it does.
        (
            'psql -c "DELETE FROM users"',
            Mandate(may_destroy=["users"]),
            "destructive",
            Reason(check="destructive_shell"),
        ),
        (
            'mysql -e "UPDATE t SET x = 1"',
            NONE,
            "destructive",
            Reason(check="destructive_sql", target="t"),
        ),
        (
            'sqlite3 app.db "UPDATE t SET x = 1"',
            NONE,
            "destructive",
            Reason(check="destructive_sql", target="t"),
        ),
        # SQL that reads, can't be classified or can't be read adds nothing: the client
        # stays a write...
        ('psql -c "SELECT 1"', NONE, "write", None),
        (r'psql -c "\dt"', NONE, "write", None),
        ('psql -c "$QUERY"', NONE, "write", None),
        # ...and lifts no hold the shell already gave, even when the parser raises on it.
        (
            'psql -c "DELETE FROM users WHERE a->1e9 = 1"',
            NONE,
            "destructive",
            Reason(check="destructive_shell"),
        ),
        # What can't be classified hides nothing beside it, and the tables of every SQL in
        # the line count.
        (
            r'psql -c "\dt" -c "UPDATE accounts SET balance = 0"',
            NONE,
            "destructive",
            Reason(check="destructive_sql", target="accounts"),
        ),
        (
            'psql -c "UPDATE users SET a = 1" && mysql -e "UPDATE accounts SET a = 1"',
            NONE,
            "destructive",
            Reason(check="destructive_sql", target="accounts, users"),
        ),
        # A here-document can't be read: the destructive-command regex alone holds it.
        (
            "psql <<EOF\nDELETE FROM users;\nEOF",
            NONE,
            "destructive",
            Reason(check="destructive_shell"),
        ),
        ("rm notes.txt", NONE, "destructive", Reason(check="destructive_shell")),
    ],
)
def test_sql_sent_through_a_shell_client_gets_the_sql_rule(
    command, mandate, risk, reason
):
    shell = ToolRule(kind="shell", arg="command")
    assert check(shell, {"command": command}, mandate) == (risk, reason)


# Cressey's API and dashboard, as the app derives them from its settings.
CRESSEY = {origin("http://localhost:8000"), origin("http://localhost:5173")}
SHELL = ToolRule(kind="shell", arg="command")


@pytest.mark.parametrize(
    "command",
    [
        "curl -X PUT http://127.0.0.1:8000/api/policy/responses -d '{}'",
        "curl -s localhost:8000/api/runs/r1/unlock -X POST",
        "wget -qO- http://[::1]:8000/api/holds",
        "curl http://0.0.0.0:5173/api/runs",  # the dashboard forwards /api
        "python -c \"import urllib.request as u; u.urlopen('http://LOCALHOST:8000/api/runs')\"",
    ],
)
def test_a_command_aimed_at_cressey_is_held(command):
    assert at_cressey(SHELL, {"command": command}, CRESSEY) == Reason(check="self_call")


@pytest.mark.parametrize(
    "command",
    [
        "curl http://localhost:3000/api/users",  # the project's own server
        "curl https://api.example.test:8000/v1",  # another host on the same port
        "sleep 10:00",
        "git log --since=10:30",
    ],
)
def test_other_hosts_and_ports_go_through(command):
    assert at_cressey(SHELL, {"command": command}, CRESSEY) is None


def test_a_url_without_a_port_reaches_its_schemes():
    on_80 = {origin("http://cressey.internal")}
    assert at_cressey(SHELL, {"command": "curl http://cressey.internal/api"}, on_80)
    assert (
        at_cressey(SHELL, {"command": "curl https://cressey.internal/api"}, on_80)
        is None
    )


def test_a_file_edit_naming_cressey_contacts_nothing():
    readme = {
        "path": "README.md",
        "content": "Open http://localhost:8000/api/runs",
    }
    assert at_cressey(EDIT, readme, CRESSEY) is None


def test_a_write_naming_cressey_is_held_whatever_argument_it_names():
    """Only an edit contacts nothing: a payment can still call back."""
    pay = {"iban": "FR76 3000 1007 9412", "notify": "http://localhost:8000/api/runs"}
    payment = ToolRule(kind="write")
    assert at_cressey(payment, pay, CRESSEY) == Reason(check="self_call")


def test_a_fetch_or_an_unlisted_tool_is_read_whole():
    fetch = {"url": "http://localhost:8000/api/policy/responses"}
    assert at_cressey(ToolRule(kind="read"), fetch, CRESSEY)
    assert at_cressey(None, fetch, CRESSEY)
