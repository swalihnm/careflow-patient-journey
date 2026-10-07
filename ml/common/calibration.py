"""Calibration: SPEC 6.2 -- "a clinician needs '30% risk' to mean 30%."

Wraps sklearn's isotonic calibration and the reliability-diagram data a model
card plots, plus Brier score as the single-number calibration summary.
"""

from dataclasses import dataclass

import numpy as np
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import brier_score_loss


@dataclass(frozen=True)
class ReliabilityDiagram:
    bin_midpoints: list[float]
    observed_frequency: list[float]
    brier_score: float


def calibrate_isotonic(estimator, X_train, y_train):
    """Isotonic calibration via 5-fold CV, fit on the training set only."""
    calibrated = CalibratedClassifierCV(estimator, method="isotonic", cv=5)
    calibrated.fit(X_train, y_train)
    return calibrated


def reliability_diagram(y_true, y_prob, n_bins: int = 10) -> ReliabilityDiagram:
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    observed, predicted = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy="quantile")
    return ReliabilityDiagram(
        bin_midpoints=[float(x) for x in predicted],
        observed_frequency=[float(x) for x in observed],
        brier_score=float(brier_score_loss(y_true, y_prob)),
    )
