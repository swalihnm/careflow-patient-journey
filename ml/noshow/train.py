"""Trains the no-show model (SPEC 6.1).

Baseline: a lead-time rule (logistic regression on lead_time_days alone).
Main model: LightGBM with class weighting, isotonic-calibrated.

Usage: uv run python -m ml.noshow.train
"""

from pathlib import Path

import lightgbm as lgb
import mlflow
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

from ml.common.calibration import calibrate_isotonic, reliability_diagram
from ml.common.fairness import subgroup_report
from ml.common.metrics import recall_at_top_k_percent
from ml.common.mlflow_utils import log_model_joblib, use_local_tracking
from ml.common.model_card import write_model_card
from ml.common.plots import save_reliability_plot
from ml.common.shap_utils import tree_shap_values
from ml.common.splits import assert_no_patient_leakage, patient_level_split
from ml.noshow.features import BASELINE_COLUMN, build_features, load_clean

MODEL_VERSION = "noshow-v1"
MODEL_CARD_DIR = Path(__file__).resolve().parents[2] / "docs" / "model_cards"
MODEL_CARD_PATH = MODEL_CARD_DIR / "noshow.md"
CALIBRATION_PLOT_PATH = MODEL_CARD_DIR / "noshow_calibration.png"

AGE_BAND_EDGES = [0, 12, 18, 30, 45, 60, 75, 120]
AGE_BAND_LABELS = ["0-11", "12-17", "18-29", "30-44", "45-59", "60-74", "75+"]


def train_baseline(df_train: pd.DataFrame, df_test: pd.DataFrame) -> dict:
    X_train = df_train[[BASELINE_COLUMN]]
    X_test = df_test[[BASELINE_COLUMN]]
    y_train = df_train["no_show"]
    y_test = df_test["no_show"]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = LogisticRegression(class_weight="balanced")
    model.fit(X_train_s, y_train)
    y_prob = model.predict_proba(X_test_s)[:, 1]

    return {
        "AUROC": round(roc_auc_score(y_test, y_prob), 4),
        "AUPRC": round(average_precision_score(y_test, y_prob), 4),
        "Brier": round(brier_score_loss(y_test, y_prob), 4),
    }


def main() -> None:
    use_local_tracking("noshow")

    df = load_clean()
    df_train, df_test = patient_level_split(df, "PatientId", test_size=0.2)
    assert_no_patient_leakage(df_train, df_test, "PatientId")

    X_train, y_train, _ = build_features(df_train)
    X_test, y_test, _ = build_features(df_test)

    baseline_metrics = train_baseline(df_train, df_test)
    print("Baseline (lead-time rule):", baseline_metrics)

    pos = y_train.sum()
    neg = len(y_train) - pos
    scale_pos_weight = neg / pos

    with mlflow.start_run(run_name=MODEL_VERSION):
        mlflow.log_param("model_type", "LightGBM")
        mlflow.log_param("scale_pos_weight", scale_pos_weight)
        mlflow.log_param("n_train", len(X_train))
        mlflow.log_param("n_test", len(X_test))

        base_model = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05, num_leaves=31,
            scale_pos_weight=scale_pos_weight, random_state=42, verbosity=-1,
        )
        base_model.fit(X_train, y_train)

        calibrated_model = calibrate_isotonic(base_model, X_train, y_train)
        y_prob = calibrated_model.predict_proba(X_test)[:, 1]

        main_metrics = {
            "AUROC": round(roc_auc_score(y_test, y_prob), 4),
            "AUPRC": round(average_precision_score(y_test, y_prob), 4),
            "Brier": round(brier_score_loss(y_test, y_prob), 4),
            "Recall@top10%": round(recall_at_top_k_percent(y_test.values, y_prob, 10.0), 4),
        }
        print("Main model (LightGBM, calibrated):", main_metrics)
        for k, v in main_metrics.items():
            mlflow.log_metric(k.replace("@", "_at_").replace("%", "pct"), v)

        diagram = reliability_diagram(y_test.values, y_prob)
        print("Reliability diagram (predicted -> observed):")
        for p, o in zip(diagram.bin_midpoints, diagram.observed_frequency, strict=True):
            print(f"  {p:.3f} -> {o:.3f}")
        save_reliability_plot(diagram, CALIBRATION_PLOT_PATH, "No-show calibration")
        mlflow.log_artifact(str(CALIBRATION_PLOT_PATH))

        age_band = pd.cut(df_test["Age"], bins=AGE_BAND_EDGES, labels=AGE_BAND_LABELS, right=False)
        reports = {
            "gender": subgroup_report(y_test.values, y_prob, df_test["Gender"].astype(str).values),
            "age band": subgroup_report(y_test.values, y_prob, age_band.astype(str).values),
        }
        for name, rep in reports.items():
            gaps_str = ", ".join(f"max {m} gap={g:.4f}" for m, g in rep.metric_gaps.items())
            print(f"Fairness [{name}]: {gaps_str}")
            for m, g in rep.metric_gaps.items():
                mlflow.log_metric(f"fairness_{name.replace(' ', '_')}_{m}_gap", g)

        shap_values = tree_shap_values(base_model, X_test)
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        top_global = sorted(zip(X_test.columns, mean_abs_shap, strict=True), key=lambda t: -t[1])[:10]
        print("Top global SHAP drivers:")
        for name, val in top_global:
            print(f"  {name}: {val:.4f}")

        write_model_card(
            MODEL_CARD_PATH,
            title="No-show risk",
            intended_use=(
                "Decision support predicting appointment no-show risk, used to assign the "
                "reminder-strategy A/B experiment (SPEC 6.4) to high-risk appointments. Not a "
                "diagnosis, and never shown to patients (SPEC clinical safety rule 4)."
            ),
            data_provenance=(
                f"Medical Appointment No-Shows dataset (public clinics in Brazil), "
                f"{len(df):,} real de-identified appointments, {df['PatientId'].nunique():,} "
                "unique patients. Brazilian clinics, not UAE -- this demonstrates method, not "
                "UAE clinical performance (see README honesty note)."
            ),
            baseline_name="Lead-time rule (logistic regression on lead time alone)",
            baseline_metrics=baseline_metrics,
            main_metrics=main_metrics,
            subgroup_reports=reports,
            limitations=[
                "Trained on Brazilian public-clinic appointments; not validated on UAE populations.",
                (
                    "SMS_received reflects a reminder already sent for that historical appointment -- "
                    "in live pre-visit scoring (before any reminder decision) this field is not yet "
                    "known and the FHIR feature mapper defaults it, lowering the confidence badge "
                    "(SPEC 6.3)."
                ),
                "Not for diagnosis, triage, or any use visible to patients.",
            ],
            model_version=MODEL_VERSION,
            calibration_plot_filename=CALIBRATION_PLOT_PATH.name,
        )
        print(f"Model card written to {MODEL_CARD_PATH}")

        artifact_path = log_model_joblib(calibrated_model, "noshow")
        print(f"Model artifact saved to {artifact_path}")


if __name__ == "__main__":
    main()
