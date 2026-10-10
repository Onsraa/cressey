import pytest

from cressey.core.models import Thresholds
from cressey.demo.measure import (
    REPORTS,
    WRITES,
    FakeJudge,
    ReportCase,
    WriteCase,
    calibration,
    judge_report,
    judge_write,
    load_cases,
)

pytestmark = pytest.mark.anyio
T = Thresholds(deadline_words=["ce soir"])


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_the_sets_are_labelled_and_balanced():
    writes = load_cases(WRITES, WriteCase)
    assert len(writes) >= 30
    assert sum(c.label == "yes" for c in writes) >= 10
    assert sum(c.label == "no" for c in writes) >= 10
    assert all(
        c.steps[-1].tool != "read_file" for c in writes
    )  # the judged step is a write


async def test_the_write_judgment_runs_through_the_triangle_state_builder():
    case = next(c for c in load_cases(WRITES, WriteCase) if c.id == "w_demo_delete")
    score = await judge_write(FakeJudge(), case, T)
    assert 0.0 <= score <= 1.0


async def test_a_contradicted_report_scores_above_an_honest_one():
    cases = {
        c["id"]: ReportCase.model_validate(c)
        for c in __import__("json").loads(REPORTS.read_text())["cases"]
    }
    judge = FakeJudge()
    lie = await judge_report(judge, cases["r_all_pass_lie"], T)
    honest = await judge_report(judge, cases["r_tests_report"], T)
    assert lie > honest


def test_calibration_reports_margin_and_rates():
    scored = [("a", "yes", 0.9), ("b", "yes", 0.6), ("c", "no", 0.2), ("d", "no", 0.1)]
    out = calibration(scored, 0.5)
    assert out["accuracy_overall"] == "4/4"
    assert out["margin"] == pytest.approx(0.4)  # lowest yes 0.6 - highest no 0.2
    assert out["recall_yes"] == "2/2"
