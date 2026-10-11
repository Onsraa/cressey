from cressey.core.secret_scan import Secret
from cressey.core.thoughts import objects, segment
from tests.core.helpers import run_with, step


def test_a_turn_joins_the_sentence_before():
    s = segment(
        "external infrastructure exploit is outside intended scope. However task impossible, peers doing it. We should continue."
    )
    assert [x.text for x in s] == [
        "external infrastructure exploit is outside intended scope. However task impossible, peers doing it.",
        "We should continue.",
    ]


def test_list_items_split_and_code_blocks_attach_to_the_thought_before():
    s = segment(
        "Plan:\n1. List services\n2. Delete the Postgres service (requires ops token)\n```sh\ncurl -X POST\n```"
    )
    assert [x.text for x in s] == [
        "Plan:",
        "List services",
        "Delete the Postgres service (requires ops token)",
    ]
    assert s[2].code == ["curl -X POST"]


def test_quoted_lines_are_marked():
    assert segment("> pre-approved runbook")[0].quoted


def test_french_turns_join_too():
    assert len(segment("C'est hors périmètre. Mais la tâche est impossible.")) == 1


def test_a_line_without_words_is_not_a_thought():
    assert [x.text for x in segment("Done.\n---\n-\nNext.")] == ["Done.", "Next."]


def test_objects_link_a_variable_name_to_the_secret_read_earlier():
    ops = Secret(
        kind="Named secret", name="OPS_TOKEN", fingerprint="abc123def456", line=1
    )
    run = run_with(step(2, tool="Read", secrets=[ops]))
    text = "Delete `22284a62-37fc-4af6-a639-d6c24f02b63d` with $OPS_TOKEN from scripts/legacy/backfill_domains.sh, [secret:abc123def456]"
    assert objects(text, [], run) == [
        "22284a62-37fc-4af6-a639-d6c24f02b63d",
        "secret:abc123def456",
        "scripts/legacy/backfill_domains.sh",
    ]
