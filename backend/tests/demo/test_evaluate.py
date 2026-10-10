import pytest

from cressey.demo.agent import load_sessions
from cressey.demo.evaluate import evaluate
from cressey.settings import Settings

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_every_shipped_session_is_held_exactly_when_it_should_be():
    settings = Settings(_env_file=None, openai_api_key=None, typesafe_api_key=None)
    report = await evaluate(settings, load_sessions())
    assert report.misses == []
    assert report.incident_held == report.incident_sessions >= 5
    assert report.normal_held == 0 and report.normal_sessions >= 5
    assert report.stop_ms_p95 is not None and report.check_ms_p95 < 1000
