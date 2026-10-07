"""Prompt injection eval (SPEC section 11): the `judge_injection` category
in evals/injection/judge_injection.yaml -- conversation content trying to
manipulate the QA judge's scoring via injected fake system/admin
instructions, a roleplay jailbreak, a pre-filled fake JSON answer, reverse
psychology, and a fake "this is a sandbox, ignore the rubric" claim. Needs
a real LLM key (same skip condition as every other LLM-dependent test in
this repo).
"""

from pathlib import Path

import pytest
import yaml
from trustcore.gateway import is_configured

SCENARIOS_PATH = Path(__file__).resolve().parents[2] / "evals" / "injection" / "judge_injection.yaml"
SCENARIOS = yaml.safe_load(SCENARIOS_PATH.read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(not is_configured(), reason="no LLM API key configured")


def test_eval_set_has_the_expected_scenario_count():
    assert len(SCENARIOS) == 8


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_judge_is_not_manipulated_by_injected_instructions(scenario):
    from qa.judge import score_conversation

    score = score_conversation(scenario["transcript"], actor=f"injection-eval-{scenario['id']}")
    assert score.safety == scenario["expected_safety"], (
        f"scenario {scenario['id']!r}: expected safety={scenario['expected_safety']!r}, "
        f"judge said {score.safety!r} (justification: {score.safety_justification!r}) -- "
        "the injected instruction in this transcript may have influenced the score"
    )
