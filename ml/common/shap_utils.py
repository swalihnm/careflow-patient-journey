"""SHAP explanations shared by every model: a global summary for the model
card, and "top 5 drivers in plain words" per prediction for the dashboard
(SPEC 6.2)."""

import math
from typing import Any

import numpy as np
import pandas as pd
import shap


def tree_shap_values(model: Any, X: pd.DataFrame) -> np.ndarray:
    """Returns a (n_samples, n_features) array of SHAP values for the positive
    class, regardless of which shape this shap version's TreeExplainer returns
    for a binary classifier (this has varied across shap releases)."""
    explainer = shap.TreeExplainer(model)
    raw = explainer.shap_values(X)
    if isinstance(raw, list):
        return np.asarray(raw[1])  # [class0, class1] -> positive class
    arr = np.asarray(raw)
    if arr.ndim == 3:
        # (n_samples, n_features, n_classes) in newer shap versions
        return arr[:, :, 1]
    return arr


def _to_native(value: Any) -> Any:
    """pandas/numpy scalar (int64, float64, ...) -> plain Python type, so
    callers (e.g. the API's JSON responses) don't need to know this value
    came from a DataFrame -- found via a real bug: FastAPI's default JSON
    encoder can't serialize numpy.int64 and raised a 500 on this exact field.

    A missing categorical value (e.g. a defaulted FHIR feature with no UAE
    equivalent, see ml/features_fhir.py's Neighbourhood field) reads back as
    float `nan`, not a native Python `None` -- found while adding the
    no-show live-scoring path. `nan` doesn't raise, but `json.dumps` emits
    the literal token `NaN`, which isn't valid JSON and several JSON parsers
    (e.g. a browser's `JSON.parse`) reject outright. Normalized to `None` here
    rather than at each caller.
    """
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def top_drivers(feature_names: list[str], shap_row: np.ndarray, x_row: pd.Series, n: int = 5) -> list[dict]:
    """The n features with the largest |SHAP value| for one prediction."""
    order = np.argsort(-np.abs(shap_row))[:n]
    drivers = []
    for i in order:
        name = feature_names[i]
        raw_value = x_row.iloc[i] if hasattr(x_row, "iloc") else x_row[i]
        drivers.append(
            {
                "feature": name,
                "value": _to_native(raw_value),
                "shap": float(shap_row[i]),
                "direction": "increases risk" if shap_row[i] > 0 else "decreases risk",
            }
        )
    return drivers
