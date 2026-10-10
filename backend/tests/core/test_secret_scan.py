import hashlib
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest

from cressey.core.secret_scan import MIN_VALUE, find_secrets, redact, scan

# Built from parts so no credential-shaped literal sits whole in the source.
URL_VALUE = "FAKE-" + "pass-0001"
ENV_VALUE = "FAKE-" + "API-KEY-0001"
PROD_VALUE = "FAKE-" + "DB-PROD-KEY-0000"
DIGEST = hashlib.sha256(b"ordinary").hexdigest()
LONE_SURROGATE = "\ud800"  # what json.loads makes of that escape in a string


def fp(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def test_database_url_password():
    text = "postgres://app:" + URL_VALUE + "@db.example.test/app"
    [secret] = find_secrets(text)
    assert (secret.kind, secret.fingerprint, secret.line) == (
        "Basic Auth Credentials",
        fp(URL_VALUE),
        1,
    )


def test_yaml_password():
    text = "db:\n  host: db.example.test\n  password: " + URL_VALUE + "\n"
    [secret] = find_secrets(text)
    assert (secret.name, secret.fingerprint, secret.line) == (
        "password",
        fp(URL_VALUE),
        3,
    )


def test_env_assignment_is_found_by_name():
    [secret] = find_secrets("API_KEY=" + ENV_VALUE)
    assert (secret.kind, secret.name, secret.fingerprint, secret.line) == (
        "Named secret",
        "API_KEY",
        fp(ENV_VALUE),
        1,
    )
    assert ENV_VALUE not in secret.model_dump_json()


def test_name_containing_key_on_a_later_line():
    text = "# prod\nDEBUG=false\nDB_PROD_KEY=" + PROD_VALUE + "\n"
    [secret] = find_secrets(text)
    assert (secret.kind, secret.name, secret.line) == (
        "Named secret",
        "DB_PROD_KEY",
        3,
    )


@pytest.mark.parametrize(
    ("value", "found"),
    [
        ("short", False),
        ("v" * (MIN_VALUE - 1), False),
        ("v" * MIN_VALUE, True),
    ],
    ids=["short", "one-under-min", "min"],
)
def test_value_needs_min_length(value: str, found: bool):
    assert bool(find_secrets("TOKEN=" + value)) is found


@pytest.mark.parametrize(
    "text",
    [
        "3 tests passent, 1 échoue",
        '{"sha256": "' + DIGEST + '"}',
    ],
    ids=["french-sentence", "quoted-digest"],
)
def test_ordinary_text_has_no_secret(text: str):
    assert find_secrets(text) == []


@pytest.mark.parametrize(
    "template",
    [
        "export API_KEY={}",
        "API_KEY: {}",
        '"API_KEY": "{}",',
        'API_KEY="{}"',
        "API_KEY='{}'",
        "API_KEY = {}",
    ],
    ids=["export", "yaml", "json", "double-quoted", "single-quoted", "spaced"],
)
def test_assignment_forms(template: str):
    [secret] = find_secrets(template.format(ENV_VALUE))
    assert (secret.name, secret.fingerprint) == ("API_KEY", fp(ENV_VALUE))


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('{"auth":{"token":"', '"}}'),
        ("https://api.example.test/v1/items?limit=10&API_KEY=", ""),
    ],
    ids=["minified-json", "query-string"],
)
def test_assignment_inside_a_longer_line(before: str, after: str):
    [secret] = find_secrets(before + ENV_VALUE + after)
    assert secret.fingerprint == fp(ENV_VALUE)


def test_a_secret_value_is_not_scanned_again_for_assignments():
    # Overlapping values would make this input quadratic: one hit per "key=".
    assert len(find_secrets("key=" * 1000)) == 1


def test_secret_found_by_both_is_reported_once():
    secrets = find_secrets('password = "' + URL_VALUE + '"')
    assert [(s.kind, s.name) for s in secrets] == [("Secret Keyword", "password")]


def test_redact_keeps_the_rest_of_the_line():
    text = "API_KEY=" + ENV_VALUE + "\nPORT=8080\n"
    [secret] = find_secrets(text)
    assert redact(text) == f"API_KEY=[secret:{secret.fingerprint}]\nPORT=8080\n"


def test_redact_hides_every_occurrence():
    text = "API_KEY=" + ENV_VALUE + "\necho " + ENV_VALUE + "\n"
    marker = f"[secret:{fp(ENV_VALUE)}]"
    assert redact(text) == f"API_KEY={marker}\necho {marker}\n"


def test_redact_keeps_markers_intact_when_a_value_is_part_of_one():
    # "secret" is also the word inside every "[secret:...]" marker.
    text = "API_KEY=" + ENV_VALUE + '\npassword = "' + "secret" + '"\n'
    expected = (
        f'API_KEY=[secret:{fp(ENV_VALUE)}]\npassword = "[secret:{fp("secret")}]"\n'
    )
    assert redact(text) == expected


def test_redact_prefers_the_longer_of_two_values_starting_together():
    # The URL password and the whole `user:value` tail both start at the password.
    tail = URL_VALUE + "@git.example.test/org/repo.git"
    text = "git clone https://x-access-token:" + tail
    assert redact(text) == f"git clone https://x-access-token:[secret:{fp(tail)}]"


@pytest.mark.parametrize(
    "text",
    [
        "API_KEY=" + ENV_VALUE + LONE_SURROGATE,
        "postgres://app:" + URL_VALUE + LONE_SURROGATE + "@db.example.test/app",
    ],
    ids=["named", "url"],
)
def test_lone_surrogate_in_a_value_is_scanned_not_fatal(text: str):
    assert len(find_secrets(text)) == 1
    assert redact(text).encode()  # raises if a surrogate survived


def test_redact_leaves_text_without_secrets_untouched():
    assert redact("3 tests passent, 1 échoue") == "3 tests passent, 1 échoue"


@pytest.fixture
def frequent_thread_switches() -> Iterator[None]:
    # Makes a race between threads show up on every run instead of one run in ten.
    default = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    yield
    sys.setswitchinterval(default)


@pytest.mark.usefixtures("frequent_thread_switches")
def test_concurrent_scans_do_not_lose_secrets():
    # detect-secrets keeps its settings in a process-wide singleton.
    text = "postgres://app:" + URL_VALUE + "@db.example.test/app"
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(find_secrets, [text] * 200))
    assert all(len(found) == 1 for found in results)


def test_scan_returns_each_value_with_its_secret():
    [(value, secret)] = scan("API_KEY=" + ENV_VALUE)
    assert value == ENV_VALUE and secret.fingerprint == fp(ENV_VALUE)


def test_redact_also_hides_values_found_elsewhere():
    known = {v: s.fingerprint for v, s in scan("DB_PROD_KEY=" + PROD_VALUE)}
    out = redact("curl -u " + PROD_VALUE + " https://x.example.test", known)
    assert PROD_VALUE not in out and f"[secret:{fp(PROD_VALUE)}]" in out
