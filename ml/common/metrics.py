"""Metrics shared across the classification models."""

import numpy as np


def recall_at_top_k_percent(y_true: np.ndarray, y_prob: np.ndarray, k_percent: float = 10.0) -> float:
    """Of all true positives, what fraction fall in the top k% of predicted
    risk? (SPEC 6.1: "recall at top 10% risk" -- the operating point for
    outreach, used instead of a plain 0.5 threshold per SPEC 6.2.)"""
    n = len(y_true)
    k = max(1, int(n * k_percent / 100))
    order = np.argsort(-y_prob)
    top_k_idx = order[:k]
    total_positives = y_true.sum()
    if total_positives == 0:
        return float("nan")
    captured = y_true[top_k_idx].sum()
    return float(captured / total_positives)
