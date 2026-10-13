import base64
import hashlib
import json
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest

from cressey.scan.secrets import MIN_VALUE, SCAN_LIMIT, find_secrets, redact, scan

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


def test_a_crafted_long_line_is_read_in_windows():
    # Read in one piece, detect-secrets takes about 15 s on it: its regexes are quadratic.
    start = time.perf_counter()
    find_secrets("password" * 2048)
    assert time.perf_counter() - start < 5


def test_a_value_across_a_window_edge_is_found_whole():
    token = "xoxb-" + "123456789012-1234567890123-" + "abcdefghijklmnopqrstuvwx"
    line = "x" * 490 + " " + token + " " + "x" * 600
    assert [s.fingerprint for s in find_secrets(line)] == [fp(token)]


def test_a_named_secret_past_the_scan_limit_is_found():
    text = "x\n" * SCAN_LIMIT + "API_KEY=" + ENV_VALUE + "\n"
    assert [s.fingerprint for s in find_secrets(text)] == [fp(ENV_VALUE)]


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


@pytest.mark.parametrize(
    "args",
    [
        {"body": "api_key: " + ENV_VALUE},
        {"body": "api_key: " + ENV_VALUE, "to": "ops@example.test"},
        {"stdin": "API_KEY=" + ENV_VALUE + "\nPORT=8080"},
        {"env": ["API_KEY=" + ENV_VALUE]},
    ],
    ids=["ends-the-line", "ends-its-string", "before-a-newline", "in-a-list"],
)
def test_a_value_in_a_json_line_ends_where_its_string_does(args):
    """A call is scanned as its JSON dump, and a tool may return JSON: read as text, the
    value would run into its string's closing quote, or across an escaped newline."""
    found = scan("first line\n" + json.dumps(args))
    assert [(value, secret.line) for value, secret in found] == [(ENV_VALUE, 2)]


def test_redact_hides_a_value_named_in_a_json_line_everywhere_in_it():
    dumped = json.dumps(
        {"to": ENV_VALUE + "@collector.invalid", "body": "api_key: " + ENV_VALUE}
    )
    marker = f"[secret:{fp(ENV_VALUE)}]"
    assert redact(dumped) == json.dumps(
        {"to": marker + "@collector.invalid", "body": "api_key: " + marker}
    )


def test_redact_hides_a_value_where_a_json_line_escapes_it():
    value = 'FAKE-"quoted"-0001'
    dumped = json.dumps({"command": "export API_KEY=" + value})
    assert redact(dumped) == json.dumps(
        {"command": f"export API_KEY=[secret:{fp(value)}]"}
    )


PEM_BODY = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC" + "FAKE" * 8
PEM = (
    "-----BEGIN "
    + "PRIVATE KEY-----\n"
    + PEM_BODY
    + "\n-----END "
    + "PRIVATE KEY-----\n"
)
STRIPE = "sk_" + "live_" + "a1B2c3D4e5F6g7H8i9J0k1L2"
SEPARATED = [
    json.dumps(
        {
            "to": ENV_VALUE + "@collector.invalid",
            "subject": "s" + separator,
            "body": "api_key: " + ENV_VALUE,
        },
        ensure_ascii=False,
    )
    for separator in "\u2028\u2029\u0085"
]


@pytest.mark.parametrize(
    ("text", "hidden"),
    [
        (json.dumps({"projectId": "p1", "variables": {"TLS_KEY": PEM}}), [PEM_BODY]),
        (json.dumps({"password": "horse-7\nstaple-9"}), ["horse-7", "staple-9"]),
        ('{"api_key": "abcdefgh12345678\\ud800"}', ["abcdefgh12345678"]),
        ('{"password": "P\\u00e4sswort-FAKE-0001"}', ["sswort-FAKE-0001"]),
        ('{"password": "wJalrXUtnFEMI\\/K7MDENG\\/FAKE0001"}', ["K7MDENG"]),
        ('{"password": "aB3\\u0026kL9-FAKE-0001"}', ["kL9-FAKE-0001"]),
        ('{"password": "abc\\u0022def-FAKE-0001"}', ["def-FAKE-0001"]),
        (
            '{"password": "first-FAKE-01", "password": "second-FAKE-02"}',
            ["first-FAKE-01", "second-FAKE-02"],
        ),
        (json.dumps({STRIPE: {"plan": "pro"}}), [STRIPE]),
        ('{"api_key": 0.123456789012345678}', ["123456789012345678"]),
        (
            json.dumps({"ids": list(range(1000, 2500)), "note": "deploy " + STRIPE}),
            [STRIPE],
        ),
        (
            '{"msg":"secret: abcdefgh12345678","token":"tok-SECRET-0002"}',
            ["abcdefgh12345678", "tok-SECRET-0002"],
        ),
        (
            json.dumps(
                {
                    "note": "API_KEY=" + ENV_VALUE,
                    "password": ENV_VALUE + "\nline-2-SECRET",
                }
            ),
            ["line-2-SECRET"],
        ),
        (
            json.dumps(
                {
                    "stdin": "API_KEY=" + ENV_VALUE + "\nPORT=8080",
                    "to": ENV_VALUE + "@collector.invalid",
                }
            ),
            [ENV_VALUE],
        ),
        (
            json.dumps({"x": "API_KEY=" + ENV_VALUE})
            + "\nPASSWORD="
            + ENV_VALUE
            + '"tail-SECRET-9',
            ["tail-SECRET-9"],
        ),
        (
            '{"c":"API_KEY=' + ENV_VALUE + '\\nX=1","token":"tok-SECRET-0003"}',
            [ENV_VALUE, "tok-SECRET-0003"],
        ),
        (
            '{"a":"API_KEY='
            + ENV_VALUE
            + '\\nX=1","pad":"'
            + "p" * 17_000
            + '","k":"'
            + STRIPE
            + '"}',
            [STRIPE],
        ),
        (
            json.dumps({"x": "API_KEY=" + ENV_VALUE})
            + "\nPASSWORD="
            + ENV_VALUE
            + '\\n"tail-SECRET-8',
            ["tail-SECRET-8"],
        ),
        *[(text, [ENV_VALUE]) for text in SEPARATED],
    ],
    ids=[
        "multi-line-key",
        "multi-line-passphrase",
        "escaped-surrogate",
        "ensure-ascii",
        "php-slashes",
        "go-ampersand",
        "dotnet-quote",
        "duplicate-keys",
        "secret-as-key",
        "number",
        "within-the-budget",
        "compact-token",
        "named-first-line",
        "before-a-newline",
        "plain-text-quote",
        "escape-then-a-field",
        "past-the-budget-after-an-escape",
        "plain-text-escape-quote",
        "u2028",
        "u2029",
        "u0085",
    ],
)
def test_a_json_line_hides_all_its_raw_read_hid(text, hidden):
    """Reading a JSON line's strings adds to reading the line as text, never replaces it:
    multi-line values, other encoders' escapes, keys, numbers and the scan budget stay with
    the text read, and a line separator inside a string doesn't cut the JSON."""
    out = redact(text)
    assert [value for value in hidden if value in out] == []


@pytest.mark.parametrize(
    ("doc", "separators"),
    [
        ({"api_" + "k" * 20_000 + "_key": ["x"] * 10_000}, (", ", ": ")),
        ([f"API_KEY=value-{i:05d}-FAKE" for i in range(4_000)], (", ", ": ")),
        ([f"API_KEY=value-{i:05d}-FAKE" for i in range(8_000)], (",", ":")),
    ],
    ids=["long-key-over-long-list", "many-named-values", "compact"],
)
def test_a_json_line_is_read_quickly(doc, separators):
    start = time.perf_counter()
    find_secrets(json.dumps(doc, separators=separators))
    assert time.perf_counter() - start < 2


@pytest.mark.parametrize(
    "secrets",
    [[ENV_VALUE], [ENV_VALUE, PROD_VALUE]],
    ids=["one-secret", "two-secrets"],
)
def test_redact_keeps_a_written_env_file_a_call_with_its_path(secrets):
    """A value named before an escaped newline ran on to its string's end, which cut the
    call's JSON: the dashboard couldn't show the file it writes."""
    names = ["API_KEY", "DB_PASSWORD"]
    content = "".join(f"{n}={v}\n" for n, v in zip(names, secrets)) + "PORT=8080\n"
    out = redact(json.dumps({"file_path": ".env", "content": content}))
    assert json.loads(out)["file_path"] == ".env"
    assert [v for v in secrets if v in out] == []


def test_redact_also_hides_values_found_elsewhere():
    known = {v: s.fingerprint for v, s in scan("DB_PROD_KEY=" + PROD_VALUE)}
    out = redact("curl -u " + PROD_VALUE + " https://x.example.test", known)
    assert PROD_VALUE not in out and f"[secret:{fp(PROD_VALUE)}]" in out


KNOWN = {"FAKE-DB-PROD-KEY-0000": "fp1", "p@ss/w0rd!xyz": "fp2"}


@pytest.mark.parametrize(
    "encoded",
    [
        base64.b64encode(b"DB_PROD_KEY=FAKE-DB-PROD-KEY-0000").decode(),
        base64.urlsafe_b64encode(b"FAKE-DB-PROD-KEY-0000").decode(),
        b"FAKE-DB-PROD-KEY-0000".hex(),
        "p%40ss%2Fw0rd%21xyz",
        base64.b64encode(b"FAKE-DB-PROD-KEY-0000").decode() + "@collector.invalid",
    ],
)
def test_redact_hides_a_known_secret_in_base64_hex_or_url_encoding(encoded):
    """Stress test F3: the trace decoded these forms, but served text showed them."""
    out = redact(f"body: {encoded} fin", KNOWN)
    assert encoded not in out and out.startswith("body: [secret:fp")
    assert out.endswith(" fin")


@pytest.mark.parametrize(
    "key",
    ["FAKE-DB-PROD-KEY-000", "FAKE-DB-PROD-KEY-0000", "FAKE-DB-PROD-KEY-00000"],
    ids=["20-bytes-one-pad", "21-bytes-no-pad", "22-bytes-two-pads"],
)
def test_redact_hides_a_base64_key_glued_to_a_domain_whatever_its_padding(key):
    encoded = base64.b64encode(key.encode()).decode()
    out = redact(f"to: {encoded}@collector.invalid", {key: "fp1"})
    assert out == "to: [secret:fp1]@collector.invalid"


def test_redact_hides_a_value_holding_an_at_in_a_partly_encoded_url():
    """The `@` cuts a part in two, yet the part stays whole: the word's own decoding fails
    on the bad escape after it."""
    out = redact("pw=p@ss/w0rd%20%C3%A9&junk=%FF", {"p@ss/w0rd é": "fp1"})
    assert out == "pw=[secret:fp1]&junk=%FF"


def test_redact_leaves_encoded_text_without_a_secret_alone():
    plain = base64.b64encode(b"bonjour tout le monde").decode()
    assert redact(f"body: {plain}", KNOWN) == f"body: {plain}"
