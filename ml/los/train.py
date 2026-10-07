"""Trains the length-of-stay model (SPEC 6.1): a point prediction plus a
quantile-based interval, admission-time features only.

Baseline: median LOS by admission type. Main model: LightGBM regression for
the point estimate, plus 10th/90th-percentile LightGBM quantile regressors
for an 80% prediction interval.

Usage: uv run python -m ml.los.train
"""

from pathlib import Path

import lightgbm as lgb
import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from ml.common.fairness import subgroup_report_regression
from ml.common.mlflow_utils import log_model_joblib, use_local_tracking
from ml.common.model_card import write_model_card
from ml.common.shap_utils import tree_shap_values
from ml.common.splits import assert_no_patient_leakage, patient_level_split
from ml.los.features import TARGET_COLUMN, build_features, load_clean

MODEL_VERSION = "los-v1"
MODEL_CARD_PATH = Path(__file__).resolve().parents[2] / "docs" / "model_cards" / "los.md"


def train_baseline(df_train: pd.DataFrame, df_test: pd.DataFrame) -> dict:
    medians = df_train.groupby("admission_type_id", observed=True)[TARGET_COLUMN].median()
    overall_median = df_train[TARGET_COLUMN].median()
    y_pred = df_test["admission_type_id"].map(medians).fillna(overall_median)
    return {"MAE": round(mean_absolute_error(df_test[TARGET_COLUMN], y_pred), 4)}


def interval_coverage(y_true: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    return float(np.mean((y_true >= lo) & (y_true <= hi)))


def main() -> None:
    use_local_tracking("los")

    df = load_clean()
    df_train, df_test = patient_level_split(df, "patient_nbr", test_size=0.2)
    assert_no_patient_leakage(df_train, df_test, "patient_nbr")

    X_train, y_train, _ = build_features(df_train)
    X_test, y_test, _ = build_features(df_test)

    baseline_metrics = train_baseline(df_train, df_test)
    print("Baseline (median by admission type):", baseline_metrics)

    with mlflow.start_run(run_name=MODEL_VERSION):
        mlflow.log_param("model_type", "LightGBM regression + quantile")
        mlflow.log_param("n_train", len(X_train))
        mlflow.log_param("n_test", len(X_test))

        point_model = lgb.LGBMRegressor(
            n_estimators=300, learning_rate=0.05, num_leaves=31, random_state=42, verbosity=-1
        )
        point_model.fit(X_train, y_train)
        y_pred = point_model.predict(X_test)

        lo_model = lgb.LGBMRegressor(
            objective="quantile", alpha=0.1, n_estimators=300, learning_rate=0.05,
            num_leaves=31, random_state=42, verbosity=-1,
        )
        hi_model = lgb.LGBMRegressor(
            objective="quantile", alpha=0.9, n_estimators=300, learning_rate=0.05,
            num_leaves=31, random_state=42, verbosity=-1,
        )
        lo_model.fit(X_train, y_train)
        hi_model.fit(X_train, y_train)
        y_lo = lo_model.predict(X_test)
        y_hi = hi_model.predict(X_test)

        main_metrics = {
            "MAE": round(mean_absolute_error(y_test, y_pred), 4),
            "80% interval coverage": round(interval_coverage(y_test.values, y_lo, y_hi), 4),
        }
        print("Main model (LightGBM):", main_metrics)
        mlflow.log_metric("mae", main_metrics["MAE"])
        mlflow.log_metric("interval_coverage_80", main_metrics["80% interval coverage"])

        reports = {
            "race": subgroup_report_regression(y_test.values, y_pred, df_test["race"].astype(str).values),
            "gender": subgroup_report_regression(y_test.values, y_pred, df_test["gender"].astype(str).values),
            "age band": subgroup_report_regression(y_test.values, y_pred, df_test["age"].astype(str).values),
        }
        for name, rep in reports.items():
            gaps_str = ", ".join(f"max {m} gap={g:.4f}" for m, g in rep.metric_gaps.items())
            print(f"Fairness [{name}]: {gaps_str}")
            for m, g in rep.metric_gaps.items():
                mlflow.log_metric(f"fairness_{name.replace(' ', '_')}_{m}_gap", g)

        shap_values = tree_shap_values(point_model, X_test)
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        top_global = sorted(zip(X_test.columns, mean_abs_shap, strict=True), key=lambda t: -t[1])[:10]
        print("Top global SHAP drivers:")
        for name, val in top_global:
            print(f"  {name}: {val:.4f}")

        write_model_card(
            MODEL_CARD_PATH,
            title="Length of stay",
            intended_use=(
                "Decision support estimating expected length of stay (with an 80% interval) at "
                "admission time, for capacity planning and care-team awareness. Not a diagnosis, "
                "and never shown to patients (SPEC clinical safety rule 4)."
            ),
            data_provenance=(
                "UCI Diabetes 130-US Hospitals (1999-2008), same cohort as the readmission model. "
                "Only admission-time features are used (SPEC 6.2 leakage control) -- discharge "
                "disposition and stay-accrued counts like lab/procedure totals are excluded."
            ),
            baseline_name="Median LOS by admission type",
            baseline_metrics=baseline_metrics,
            main_metrics=main_metrics,
            subgroup_reports=reports,
            limitations=[
                "Trained on US hospital data from 1999-2008; not validated on UAE populations.",
                (
                    "Only admission-time features are used, which caps achievable accuracy relative "
                    "to a model allowed to see mid-stay information -- by design, to avoid leakage."
                ),
                "Not for diagnosis, triage, or any use visible to patients.",
            ],
            model_version=MODEL_VERSION,
        )
        print(f"Model card written to {MODEL_CARD_PATH}")

        log_model_joblib({"point": point_model, "lo": lo_model, "hi": hi_model}, "los")


if __name__ == "__main__":
    main()
