"""Subgroup fairness reporting (SPEC 6.2): "compare AUROC and calibration
across age bands, gender and race groups... report gaps honestly." Uses
Fairlearn's MetricFrame, the same tool its own tutorials use on this exact
UCI diabetes dataset.
"""

from dataclasses import dataclass

import numpy as np
from fairlearn.metrics import MetricFrame
from sklearn.metrics import brier_score_loss, mean_absolute_error, roc_auc_score


def _safe_auroc(y_true, y_prob) -> float:
    if len(np.unique(y_true)) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, y_prob))


def _count(y_true, _y_prob) -> int:
    return len(y_true)


@dataclass(frozen=True)
class SubgroupReport:
    by_group: dict[str, dict[str, float]]
    metric_gaps: dict[str, float]  # metric name -> (max - min) across groups


def _build_report(by_group: dict) -> SubgroupReport:
    metric_names = [k for k in next(iter(by_group.values()), {}) if k != "n"]
    gaps = {}
    for m in metric_names:
        vals = [v[m] for v in by_group.values() if v[m] == v[m]]  # drop NaN
        gaps[m] = float(max(vals) - min(vals)) if len(vals) > 1 else 0.0
    return SubgroupReport(by_group=by_group, metric_gaps=gaps)


def subgroup_report(y_true, y_prob, sensitive_features) -> SubgroupReport:
    """For binary classifiers: AUROC + Brier score per subgroup."""
    mf = MetricFrame(
        metrics={"auroc": _safe_auroc, "brier": brier_score_loss, "n": _count},
        y_true=y_true,
        y_pred=y_prob,
        sensitive_features=sensitive_features,
    )
    return _build_report(mf.by_group.to_dict(orient="index"))


def subgroup_report_regression(y_true, y_pred, sensitive_features) -> SubgroupReport:
    """For regressors (the LOS model): MAE per subgroup."""
    mf = MetricFrame(
        metrics={"mae": mean_absolute_error, "n": lambda yt, yp: len(yt)},
        y_true=y_true,
        y_pred=y_pred,
        sensitive_features=sensitive_features,
    )
    return _build_report(mf.by_group.to_dict(orient="index"))
