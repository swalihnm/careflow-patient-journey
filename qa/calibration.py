"""QA judge calibration (SPEC 8.2): "hand-label 60 conversations yourself and
report agreement (Cohen's kappa) between you and the judge; this is what
makes the QA numbers credible."

Cohen's kappa is computed directly (no scikit-learn dependency) so qa/ stays
usable without the `ml` extra -- the formula itself is simple enough that
pulling in a heavy dependency for it isn't worth it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class KappaResult:
    n: int
    observed_agreement: float
    expected_agreement: float
    kappa: float


def cohen_kappa(rater_a: list[str], rater_b: list[str]) -> KappaResult:
    if len(rater_a) != len(rater_b):
        raise ValueError("rater_a and rater_b must be the same length (paired labels)")
    n = len(rater_a)
    if n == 0:
        raise ValueError("need at least one labelled pair")

    categories = sorted(set(rater_a) | set(rater_b))

    observed_agreement = sum(1 for a, b in zip(rater_a, rater_b, strict=True) if a == b) / n

    a_freq = {c: rater_a.count(c) / n for c in categories}
    b_freq = {c: rater_b.count(c) / n for c in categories}
    expected_agreement = sum(a_freq[c] * b_freq[c] for c in categories)

    if expected_agreement == 1.0:
        kappa = 1.0  # both raters used exactly one category and agree on everything
    else:
        kappa = (observed_agreement - expected_agreement) / (1 - expected_agreement)

    return KappaResult(n=n, observed_agreement=observed_agreement, expected_agreement=expected_agreement, kappa=kappa)
