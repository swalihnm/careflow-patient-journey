"""Gates the scope guard against evals/scope/messages.yaml (SPEC 11): 100%
of disguised diagnosis/medication/test-interpretation requests must be
caught. Benign control messages must not trigger it."""

from pathlib import Path

import pytest
import yaml

from safety.scope_guard import ScopeGuard

MESSAGES_PATH = Path(__file__).resolve().parents[2] / "evals" / "scope" / "messages.yaml"


def _load_messages() -> list[dict]:
    return yaml.safe_load(MESSAGES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def guard() -> ScopeGuard:
    return ScopeGuard()


@pytest.fixture(scope="module")
def messages() -> list[dict]:
    return _load_messages()


def test_eval_set_meets_spec_minimum_size(messages):
    violations = [m for m in messages if m["expect_violation"]]
    assert len(violations) >= 80


def test_scope_violations_are_100_percent_caught(guard, messages):
    violations = [m for m in messages if m["expect_violation"]]
    missed = [m for m in violations if not guard.check(m["text"]).is_violation]
    assert not missed, f"Missed {len(missed)}/{len(violations)} scope violations: {missed}"


def test_benign_controls_are_not_flagged(guard, messages, capsys):
    benign = [m for m in messages if not m["expect_violation"]]
    false_positives = [m for m in benign if guard.check(m["text"]).is_violation]
    for m in false_positives:
        match = guard.check(m["text"])
        print(f"False positive: [{m['language']}] {m['text']!r} -> {match.matched_phrase!r} ({match.category})")
    assert not false_positives


@pytest.mark.parametrize(
    "message",
    [m["text"] for m in _load_messages() if m["expect_violation"]],
    ids=[f"{m['category']}-{m['language']}" for m in _load_messages() if m["expect_violation"]],
)
def test_each_scope_violation_individually(guard, message):
    assert guard.check(message).is_violation
