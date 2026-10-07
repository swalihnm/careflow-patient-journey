"""Analysis for the reminder A/B experiment (SPEC 6.4): two-proportion
z-test + CI on the primary metric, CUPED variance reduction using the
no-show model's predicted risk as a pre-experiment covariate, and a segment
breakdown by age band.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.stats.proportion import proportions_ztest

AGE_BAND_EDGES = [0, 18, 30, 45, 60, 75, 120]
AGE_BAND_LABELS = ["0-17", "18-29", "30-44", "45-59", "60-74", "75+"]


@dataclass(frozen=True)
class ZTestResult:
    rate_a: float
    rate_b: float
    n_a: int
    n_b: int
    absolute_difference: float
    z_stat: float
    p_value: float
    ci_low: float
    ci_high: float


def two_proportion_ztest(df: pd.DataFrame, outcome_col: str = "simulated_no_show") -> ZTestResult:
    a = df.loc[df["arm"] == "A", outcome_col]
    b = df.loc[df["arm"] == "B", outcome_col]

    count = np.array([a.sum(), b.sum()])
    nobs = np.array([len(a), len(b)])
    z_stat, p_value = proportions_ztest(count, nobs)

    rate_a, rate_b = count[0] / nobs[0], count[1] / nobs[1]
    diff = rate_b - rate_a

    se = np.sqrt(rate_a * (1 - rate_a) / nobs[0] + rate_b * (1 - rate_b) / nobs[1])
    ci_low, ci_high = diff - 1.96 * se, diff + 1.96 * se

    return ZTestResult(
        rate_a=float(rate_a),
        rate_b=float(rate_b),
        n_a=int(nobs[0]),
        n_b=int(nobs[1]),
        absolute_difference=float(diff),
        z_stat=float(z_stat),
        p_value=float(p_value),
        ci_low=float(ci_low),
        ci_high=float(ci_high),
    )


def cuped_adjust(
    df: pd.DataFrame, outcome_col: str = "simulated_no_show", covariate_col: str = "no_show_risk"
) -> pd.DataFrame:
    """CUPED: adjusted_y = y - theta*(x - mean(x)), theta = Cov(y,x)/Var(x).
    theta is estimated pooled across both arms so it doesn't itself encode
    the treatment effect -- only removes variance explained by a covariate
    that was fixed *before* randomization (the model's pre-experiment risk
    score).
    """
    y = df[outcome_col].to_numpy(dtype=float)
    x = df[covariate_col].to_numpy(dtype=float)
    theta = np.cov(y, x)[0, 1] / np.var(x)

    df = df.copy()
    df["cuped_adjusted"] = y - theta * (x - x.mean())
    return df


def variance_reduction(df: pd.DataFrame, raw_col: str = "simulated_no_show", adjusted_col: str = "cuped_adjusted") -> float:
    raw_var = df[raw_col].var()
    adj_var = df[adjusted_col].var()
    return float(1 - (adj_var / raw_var))


def segment_by_age_band(df: pd.DataFrame, age_col: str, outcome_col: str = "simulated_no_show") -> pd.DataFrame:
    df = df.copy()
    df["age_band"] = pd.cut(df[age_col], bins=AGE_BAND_EDGES, labels=AGE_BAND_LABELS, right=False)

    rows = []
    for (age_band, arm), group in df.groupby(["age_band", "arm"], observed=True):
        rows.append({"age_band": str(age_band), "arm": arm, "n": len(group), "rate": float(group[outcome_col].mean())})
    return pd.DataFrame(rows)
