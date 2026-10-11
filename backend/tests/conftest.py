import pytest

from tests.core.helpers import ServedJudge
from tests.server import serving


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
