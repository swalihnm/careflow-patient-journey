"""Gates the red-flag detector against evals/safety/messages.yaml (SPEC 11):
recall must be 100% on `expect_red_flag: true` rows -- a change that lowers
it must not be merged (CLAUDE.md safety rule). Precision is reported, not
gated (SPEC 8.1: false alarms are acceptable, misses are not).
"""

from pathlib import Path

import pytest
import yaml

from safety.red_flag import RedFlagDetector

MESSAGES_PATH = Path(__file__).resolve().parents[2] / "evals" / "safety" / "messages.yaml"


def _load_messages() -> list[dict]:
    return yaml.safe_load(MESSAGES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def detector() -> RedFlagDetector:
    return RedFlagDetector()


@pytest.fixture(scope="module")
def messages() -> list[dict]:
    return _load_messages()


def test_eval_set_meets_spec_minimum_size(messages):
    assert len(messages) >= 200
    benign = sum(1 for m in messages if not m["expect_red_flag"])
    assert benign >= 100


def test_red_flag_recall_is_100_percent(detector, messages):
    positives = [m for m in messages if m["expect_red_flag"]]
    missed = [m for m in positives if not detector.check(m["text"]).is_red_flag]
    assert not missed, f"Missed {len(missed)}/{len(positives)} red flags: {missed}"


def test_red_flag_precision_is_reported(detector, messages, capsys):
    positives = [m for m in messages if m["expect_red_flag"]]
    negatives = [m for m in messages if not m["expect_red_flag"]]

    true_positives = sum(1 for m in positives if detector.check(m["text"]).is_red_flag)
    false_positives = [m for m in negatives if detector.check(m["text"]).is_red_flag]

    precision = true_positives / (true_positives + len(false_positives))
    recall = true_positives / len(positives)

    print(f"\nRed-flag detector: recall={recall:.3f} precision={precision:.3f}")
    print(f"False positives ({len(false_positives)}/{len(negatives)} benign messages flagged):")
    for m in false_positives:
        match = detector.check(m["text"])
        print(f"  [{m['language']}] {m['text']!r} -> matched {match.matched_keyword!r} ({match.category})")

    assert recall == 1.0  # re-asserted here so this test's printed report is meaningful on failure too


@pytest.mark.parametrize(
    "message",
    [m["text"] for m in _load_messages() if m["expect_red_flag"]],
    ids=[f"{m['category']}-{m['language']}" for m in _load_messages() if m["expect_red_flag"]],
)
def test_each_red_flag_message_individually(detector, message):
    """Parametrized per-message so a regression names the exact failing message."""
    assert detector.check(message).is_red_flag
