"""What a reader of the run sees of what its calls returned."""

import time

from cressey.engine.reading import redacted
from cressey.scan.secrets import SCAN_LIMIT, fingerprint
from tests.helpers import run_with, step

KEY = "s3cr3t-value-of-the-run"


def test_a_result_read_again_is_not_scanned_again():
    """Its secrets were found and kept when it came in (`Engine.after`), so a reader hides
    those: the scan, under a process-wide lock, runs once per result, not once per read
    (the report check reads every step's)."""
    page = f"token: {KEY}\n" + "plain row of text\n" * (SCAN_LIMIT // 18)
    run = run_with(*(step(n, "read_file", result=page) for n in range(1, 51)))
    run.known = {KEY: fingerprint(KEY)}
    started = time.perf_counter()
    shown = redacted(run, run.steps)
    took = time.perf_counter() - started
    assert len(shown) == 50
    assert all(KEY not in text for text in shown.values())
    assert all(f"[secret:{fingerprint(KEY)}]" in text for text in shown.values())
    assert took < 0.5, took
