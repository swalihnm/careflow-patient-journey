"""Reminder A/B experiment (SPEC 6.4). Needs the trained no-show model
(`uv run python -m ml.noshow.train`) -- pure computation otherwise, no DB
or FHIR needed."""

import numpy as np
import pandas as pd
import pytest

from ml.experiment.analyze import (
    cuped_adjust,
    segment_by_age_band,
    two_proportion_ztest,
    variance_reduction,
)
from ml.experiment.power import required_sample_size
from ml.experiment.simulate import (
    ARTIFACTS_DIR,
    assign_arms,
    build_experiment_population,
    simulate_outcomes,
)

pytestmark = pytest.mark.skipif(
    not (ARTIFACTS_DIR / "noshow.joblib").exists(),
    reason="no-show model not trained yet (uv run python -m ml.noshow.train)",
)


def test_arm_assignment_and_outcome_are_independently_seeded():
    """Regression test for a real bug found during development: reusing the
    identical seed for arm assignment (.choice) and outcome simulation
    (.binomial) as two separate `default_rng(seed)` calls made them draw the
    *same* underlying uniform sequence, which silently correlated which arm
    a row got with its simulated outcome (verified: arm=='A' predicted the
    outcome draw's uniform being <0.5 with 100% accuracy). Per-arm no-show
    rates should reflect the assumed effect size, not an artifact of shared
    RNG state.
    """
    population = build_experiment_population(random_state=123)
    rates = population.groupby("arm")["simulated_no_show"].mean()

    # Both arms draw from a similar risk distribution (same random split),
    # so their raw risk means should be close...
    risk_by_arm = population.groupby("arm")["no_show_risk"].mean()
    assert abs(risk_by_arm["A"] - risk_by_arm["B"]) < 0.03

    # ...but arm B's *outcome* rate should be around 15% relatively lower
    # than A's, not wildly different (the bug produced ~0.4% vs ~56%).
    relative_diff = (rates["A"] - rates["B"]) / rates["A"]
    assert 0.05 < relative_diff < 0.30, f"expected ~15% relative reduction, got {relative_diff:.1%}"


def test_different_random_states_give_different_but_plausible_populations():
    pop1 = build_experiment_population(random_state=1)
    pop2 = build_experiment_population(random_state=2)
    assert not pop1["simulated_no_show"].equals(pop2["simulated_no_show"])
    for pop in (pop1, pop2):
        assert 0.15 < pop["simulated_no_show"].mean() < 0.55


def test_power_analysis_returns_sane_sample_size():
    result = required_sample_size(baseline_rate=0.30, absolute_reduction=0.03)
    assert result.required_n_per_arm > 0
    assert result.target_rate == pytest.approx(0.27)


def test_ztest_detects_a_real_simulated_difference():
    rng = np.random.default_rng(0)
    n = 5000
    df = pd.DataFrame(
        {
            "arm": ["A"] * n + ["B"] * n,
            "simulated_no_show": np.concatenate(
                [rng.binomial(1, 0.30, n), rng.binomial(1, 0.20, n)]
            ),
        }
    )
    result = two_proportion_ztest(df)
    assert result.p_value < 0.001
    assert result.absolute_difference < 0


def test_cuped_reduces_variance_for_a_correlated_continuous_outcome():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, 2000)
    y = 2 * x + rng.normal(0, 0.5, 2000)  # strongly correlated with x
    df = pd.DataFrame({"simulated_no_show": y, "no_show_risk": x})
    adjusted = cuped_adjust(df)
    reduction = variance_reduction(adjusted)
    assert reduction > 0.5  # a strong covariate should cut variance substantially


def test_segment_by_age_band_covers_both_arms():
    df = pd.DataFrame(
        {
            "Age": [5, 25, 40, 70, 10, 30, 50, 80],
            "arm": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "simulated_no_show": [0, 1, 0, 1, 0, 0, 1, 1],
        }
    )
    segments = segment_by_age_band(df, age_col="Age")
    assert set(segments["arm"]) == {"A", "B"}
    assert segments["n"].sum() == len(df)


def test_assign_arms_is_roughly_balanced():
    df = pd.DataFrame({"no_show_risk": np.linspace(0.2, 0.6, 2000)})
    assigned = assign_arms(df, random_state=7)
    counts = assigned["arm"].value_counts()
    assert 0.4 < counts["A"] / len(assigned) < 0.6


def test_simulate_outcomes_respects_relative_reduction():
    df = pd.DataFrame({"arm": ["A"] * 5000 + ["B"] * 5000, "no_show_risk": [0.4] * 10000})
    result = simulate_outcomes(df, relative_reduction=0.20, random_state=99)
    rate_a = result.loc[result["arm"] == "A", "simulated_no_show"].mean()
    rate_b = result.loc[result["arm"] == "B", "simulated_no_show"].mean()
    assert rate_a == pytest.approx(0.4, abs=0.03)
    assert rate_b == pytest.approx(0.32, abs=0.03)
