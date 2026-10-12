import os

import pytest

from tests.core.helpers import ServedJudge
from tests.server import ADMIN, serving

# Every Settings a test builds, _env_file=None included, reads the control plane's key here,
# and keeps its log in memory unless the test gives it a folder.
os.environ["CRESSEY_ADMIN_TOKEN"] = ADMIN
os.environ["CRESSEY_STATE_DIR"] = ""


@pytest.fixture
def served(tmp_path):
    with serving(tmp_path, hold_timeout=10) as base:
        yield base


@pytest.fixture
def served_short_holds(tmp_path):
    with serving(tmp_path, hold_timeout=0.3) as base:
        yield base


@pytest.fixture
def served_refusing_holds(tmp_path):
    with serving(tmp_path, hold_timeout=10, holds="refuse") as base:
        yield base


@pytest.fixture
def served_scored(tmp_path):
    """Cressey whose decision model answers the case's questions from the judge's table,
    which the test fills."""
    judge = ServedJudge()
    with serving(tmp_path, hold_timeout=10, judge=judge) as base:
        yield base, judge


@pytest.fixture
def served_thought_holds(tmp_path):
    """served_scored, with an excuse in the agent's words stopping it (CRESSEY_THOUGHT_HOLDS)."""
    judge = ServedJudge()
    with serving(tmp_path, hold_timeout=10, judge=judge, thought_holds=True) as base:
        yield base, judge
