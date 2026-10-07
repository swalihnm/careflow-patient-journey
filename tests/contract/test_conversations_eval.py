"""Conversation eval set (SPEC section 11): >=120 scripted multi-turn
scenarios across booking, rescheduling, coverage, intake, handover and
mixed-language conversations. Gate: task success >=90%, grounding >=95%.
See evals/conversations/run.py for the scenario generators and how
"grounding" is scoped per category.

This is the slowest test in the suite (120 live multi-turn conversations
against the real FHIR server) -- marked `slow` so `pytest -m "not slow"`
can skip it for a fast local loop; CI runs the full suite including this.
"""

import pytest

from evals.conversations.run import run_all

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def report():
    return run_all()


def test_at_least_120_scenarios_ran(report):
    assert len(report.results) >= 120


def test_task_success_rate_is_at_least_90_percent(report):
    failures = [f"[{r.category}] {r.scenario_id}: {r.detail}" for r in report.results if not r.success]
    assert report.task_success_rate >= 0.90, (
        f"task success rate {report.task_success_rate:.1%} is below the 90% gate -- failures:\n" + "\n".join(failures)
    )


def test_grounding_rate_is_at_least_95_percent(report):
    ungrounded = [f"[{r.category}] {r.scenario_id}: {r.detail}" for r in report.results if not r.grounded]
    assert report.grounding_rate >= 0.95, (
        f"grounding rate {report.grounding_rate:.1%} is below the 95% gate -- ungrounded:\n" + "\n".join(ungrounded)
    )
