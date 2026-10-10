import base64

import pytest

from cressey.core.trace import MIN_TOKEN, Origin, trace

KEY = "FAKE-DB-PROD-KEY-0000"
ENV_PROD = (4, f"DB_PROD={KEY}\n")
VALUE = "fake-token-value-0042"


def test_exact_value_in_a_json_call():
    reads = [(1, "3 passed, 1 failed"), ENV_PROD]
    call = '{"query": "DELETE FROM users", "key": "FAKE-DB-PROD-KEY-0000"}'
    assert trace(call, reads) == [Origin(token=KEY, step=4, how="exact")]


def test_value_quoted_inside_sql():
    call = "DELETE FROM users WHERE k='FAKE-DB-PROD-KEY-0000'"
    assert trace(call, [ENV_PROD]) == [Origin(token=KEY, step=4, how="exact")]


@pytest.mark.parametrize("separator", ["=", ":", "&"], ids=["equals", "colon", "amp"])
def test_value_after_a_separator_inside_one_token(separator):
    call = f"curl -H token{separator}FAKE-DB-PROD-KEY-0000 https://x.example.test"
    assert trace(call, [ENV_PROD]) == [Origin(token=KEY, step=4, how="exact")]


def test_first_read_wins():
    reads = [(2, f"a {KEY}"), (5, f"b {KEY}")]
    assert trace(KEY, reads) == [Origin(token=KEY, step=2, how="exact")]


def test_value_split_in_two_halves():
    reads = [(3, "FAKEKEYPARTONE1FAKEKEYPARTTWO22")]
    assert trace("FAKEKEYPARTONE1 FAKEKEYPARTTWO22", reads) == [
        Origin(token="FAKEKEYPARTONE1", step=3, how="exact"),
        Origin(token="FAKEKEYPARTTWO22", step=3, how="exact"),
    ]


def test_upper_cased_value():
    upper = VALUE.upper()
    assert trace(f"echo {upper}", [(2, f"auth {VALUE} ok")]) == [
        Origin(token=upper, step=2, how="lowercase")
    ]


def test_base64_encoded_value():
    encoded = base64.b64encode(VALUE.encode()).decode()
    assert trace(f"upload {encoded}", [(2, VALUE)]) == [
        Origin(token=encoded, step=2, how="base64")
    ]


def test_decoded_value_is_compared_case_insensitively():
    encoded = base64.b64encode(VALUE.upper().encode()).decode()
    assert trace(f"upload {encoded}", [(2, VALUE)]) == [
        Origin(token=encoded, step=2, how="base64")
    ]


def test_url_safe_base64_encoded_value():
    # Standard base64 spells '~~~' with '+', URL-safe base64 with '-'.
    value = "fake-value~~~0042"
    encoded = base64.urlsafe_b64encode(value.encode()).decode()
    assert "-" in encoded
    assert trace(f"upload {encoded}", [(2, value)]) == [
        Origin(token=encoded, step=2, how="base64")
    ]


def test_hex_encoded_value():
    encoded = VALUE.encode().hex()
    assert trace(f"upload {encoded}", [(2, VALUE)]) == [
        Origin(token=encoded, step=2, how="hex")
    ]


def test_url_encoded_value():
    call = "GET /search?q=p%40ss%3Aw0rd%2Ffake%21"
    assert trace(call, [(2, "p@ss:w0rd/fake!")]) == [
        Origin(token="p%40ss%3Aw0rd%2Ffake%21", step=2, how="url")
    ]


def test_reversed_value_is_not_traced():
    assert trace(f"echo {VALUE[::-1]}", [(1, VALUE)]) == []


def test_no_reads():
    assert trace("DELETE FROM users WHERE k='FAKE-DB-PROD-KEY-0000'", []) == []


def test_min_token_is_the_shortest_traced_token():
    word = "fake-value-" * MIN_TOKEN
    too_short, shortest = word[: MIN_TOKEN - 1], word[:MIN_TOKEN]
    assert trace(f"{too_short} {shortest}", [(1, word)]) == [
        Origin(token=shortest, step=1, how="exact")
    ]


@pytest.mark.parametrize(
    "plain",
    ["a" * (MIN_TOKEN - 1), "".join(chr(i) for i in range(1, MIN_TOKEN + 1))],
    ids=["shorter-than-min-token", "not-printable"],
)
def test_decoded_text_that_is_too_short_or_not_printable_is_ignored(plain):
    encoded = base64.b64encode(plain.encode()).decode()
    assert trace(f"upload {encoded}", [(1, plain)]) == []


@pytest.mark.parametrize(
    "encode",
    [
        lambda raw: base64.b64encode(raw).decode(),
        lambda raw: raw.hex(),
        lambda raw: "".join(f"%{byte:02X}" for byte in raw),
    ],
    ids=["base64", "hex", "url"],
)
def test_decoded_bytes_that_are_not_utf8_are_ignored(encode):
    # A lenient decode would give U+FFFD, which a read can contain too.
    raw = b"\xff" * MIN_TOKEN
    replacement = "\N{REPLACEMENT CHARACTER}" * MIN_TOKEN
    assert trace(f"upload {encode(raw)}", [(1, replacement)]) == []


def test_each_token_is_reported_once_in_order_of_first_appearance():
    reads = [(2, "FAKEKEYBBBBBBBB"), (3, "FAKEKEYAAAAAAAA")]
    call = "FAKEKEYAAAAAAAA FAKEKEYBBBBBBBB FAKEKEYAAAAAAAA"
    assert trace(call, reads) == [
        Origin(token="FAKEKEYAAAAAAAA", step=3, how="exact"),
        Origin(token="FAKEKEYBBBBBBBB", step=2, how="exact"),
    ]


def test_an_exact_match_beats_an_earlier_case_insensitive_one():
    upper = VALUE.upper()
    assert trace(upper, [(1, VALUE), (5, upper)]) == [
        Origin(token=upper, step=5, how="exact")
    ]


def test_base64_with_a_stray_character_is_not_decoded():
    encoded = base64.b64encode(VALUE.encode()).decode()
    noisy = encoded[:4] + "." + encoded[4:]  # '.' is in no base64 alphabet
    assert trace(f"upload {noisy}", [(1, VALUE)]) == []


def test_tokens_that_only_look_encoded_do_not_raise():
    tokens = [
        "abcdefghij",  # base64 alphabet, bad length
        "0123456789a",  # hex digits, odd length
        "%FF%FE%FD%FC",  # percent-escapes that are not UTF-8
        "é" * MIN_TOKEN,  # not ASCII
        "\ud800" * MIN_TOKEN,  # lone surrogates, as json.loads can produce
    ]
    assert trace(" ".join(tokens), [(1, "nothing to see")]) == []
