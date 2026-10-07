"""Simulates the reminder A/B experiment (SPEC 6.4) on real patients from the
no-show test set, scored by the trained no-show model -- the *population* and
*risk scores* are real; the *outcomes* are simulated from an assumed effect
size, clearly labelled as such everywhere this data is used. There is no live
experiment to observe; this demonstrates the analysis method the real one
would use.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.common.splits import patient_level_split
from ml.noshow.features import build_features, load_clean

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"

HIGH_RISK_PERCENTILE = 0.70  # top 30% by predicted no-show risk get the reminder experiment
ASSUMED_RELATIVE_REDUCTION = 0.15  # arm B (two-step reminder) assumed 15% relative reduction vs arm A


def load_scored_population(random_state: int = 42) -> pd.DataFrame:
    """Real patients (not simulated), scored by the trained no-show model."""
    model = joblib.load(ARTIFACTS_DIR / "noshow.joblib")
    df = load_clean()
    _train, test_df = patient_level_split(df, "PatientId", test_size=0.3, random_state=random_state)
    X, _y, _patient_id = build_features(test_df)
    prob = model.predict_proba(X)[:, 1]

    result = test_df.reset_index(drop=True).copy()
    result["no_show_risk"] = prob
    return result


def select_high_risk(df: pd.DataFrame, percentile: float = HIGH_RISK_PERCENTILE) -> pd.DataFrame:
    threshold = df["no_show_risk"].quantile(percentile)
    return df[df["no_show_risk"] >= threshold].copy()


def assign_arms(df: pd.DataFrame, random_state: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(random_state)
    df = df.copy()
    df["arm"] = rng.choice(["A", "B"], size=len(df), p=[0.5, 0.5])
    return df


def simulate_outcomes(
    df: pd.DataFrame, relative_reduction: float = ASSUMED_RELATIVE_REDUCTION, random_state: int = 42
) -> pd.DataFrame:
    """Arm A (single SMS, control): simulated outcome ~ Bernoulli(model's
    predicted risk). Arm B (two-step reminder): ~ Bernoulli(risk * (1 -
    relative_reduction)). A SIMULATION, not an observed result.
    """
    rng = np.random.default_rng(random_state)
    df = df.copy()
    effective_prob = np.where(
        df["arm"] == "B", df["no_show_risk"] * (1 - relative_reduction), df["no_show_risk"]
    )
    df["simulated_no_show"] = rng.binomial(1, effective_prob)

    # Guardrail metric: cancellations. No assumed arm effect -- simulated
    # from a flat base rate, purely to demonstrate the guardrail-metric
    # analysis pattern, not to claim a real cancellation effect.
    df["simulated_cancellation"] = rng.binomial(1, 0.05, size=len(df))
    return df


def build_experiment_population(random_state: int = 42) -> pd.DataFrame:
    # Each step below needs its OWN seed, not the same one reused: numpy's
    # Generator(seed) is a deterministic bit stream, so `default_rng(42)`
    # used for arm assignment (.choice) and `default_rng(42)` used again for
    # the outcome draw (.binomial) consume the *identical* underlying
    # uniform sequence -- which silently correlates "which arm a row got"
    # with "what its simulated outcome was" (verified: arm == 'A' predicted
    # the outcome-draw's underlying uniform being < 0.5 with 100% accuracy),
    # producing a wildly biased A-vs-B split with no error or warning. Three
    # independent seeds derived from one parent keeps the whole pipeline
    # reproducible from `random_state` alone without this trap.
    parent_rng = np.random.default_rng(random_state)
    split_seed, arm_seed, outcome_seed = (int(s) for s in parent_rng.integers(0, 2**31 - 1, size=3))

    scored = load_scored_population(split_seed)
    high_risk = select_high_risk(scored)
    assigned = assign_arms(high_risk, arm_seed)
    return simulate_outcomes(assigned, random_state=outcome_seed)
