"""Cohen's kappa (SPEC 8.2 calibration) -- verified against known textbook
values, not just internal consistency."""

import pytest

from qa.calibration import cohen_kappa


def test_perfect_agreement_gives_kappa_1():
    labels = ["pass", "fail", "pass", "pass", "fail"]
    result = cohen_kappa(labels, labels)
    assert result.kappa == pytest.approx(1.0)
    assert result.observed_agreement == 1.0


def test_chance_level_agreement_gives_kappa_near_0():
    # Two raters each split 50/50 but never agree -> kappa should be near 0.
    rater_a = ["pass", "fail"] * 25
    rater_b = ["fail", "pass"] * 25
    result = cohen_kappa(rater_a, rater_b)
    assert result.kappa == pytest.approx(-1.0, abs=0.01)  # systematic disagreement, not just chance


def test_known_textbook_example():
    # Classic worked example: 2 raters, yes/no, 50 items.
    # Agree-yes: 20, agree-no: 15, disagree: 15 (10 + 5)
    rater_a = ["yes"] * 30 + ["no"] * 20
    rater_b = ["yes"] * 20 + ["no"] * 5 + ["yes"] * 10 + ["no"] * 15
    result = cohen_kappa(rater_a, rater_b)
    assert 0 < result.kappa < 1
    assert result.n == 50


def test_mismatched_lengths_raises():
    with pytest.raises(ValueError):
        cohen_kappa(["pass"], ["pass", "fail"])


def test_empty_raises():
    with pytest.raises(ValueError):
        cohen_kappa([], [])


def test_kappa_matches_independently_computed_reference_value():
    # po/pe/kappa for this exact input computed by hand (independently of
    # qa.calibration's code) before writing this assertion: po=0.5, pe=0.34,
    # kappa=(0.5-0.34)/(1-0.34)=0.242424...
    rater_a = ["a", "b", "c", "a", "b", "c", "a", "b", "c", "a"]
    rater_b = ["a", "b", "c", "a", "b", "a", "b", "c", "a", "b"]
    result = cohen_kappa(rater_a, rater_b)
    assert result.kappa == pytest.approx(0.242424, abs=1e-5)
