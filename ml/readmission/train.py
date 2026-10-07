"""Trains the 30-day readmission model (SPEC 6.1).

Baseline: logistic regression on prior admissions (number_inpatient) + length
of stay. Main model: LightGBM with class weighting, isotonic-calibrated.

Usage: uv run python -m ml.readmission.train
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
from ml.readmission.features import BASELINE_COLUMNS, build_features, load_clean

MODEL_VERSION = "readmission-v1"
MODEL_CARD_DIR = Path(__file__).resolve().parents[2] / "docs" / "model_cards"
MODEL_CARD_PATH = MODEL_CARD_DIR / "readmission.md"
CALIBRATION_PLOT_PATH = MODEL_CARD_DIR / "readmission_calibration.png"


def train_baseline(df_train: pd.DataFrame, df_test: pd.DataFrame) -> dict:
    X_train = df_train[BASELINE_COLUMNS].fillna(0)
    X_test = df_test[BASELINE_COLUMNS].fillna(0)
    y_train = df_train["readmitted_30"]
    y_test = df_test["readmitted_30"]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = LogisticRegression(class_weight="balanced", max_iter=1000)
    model.fit(X_train_s, y_train)
    y_prob = model.predict_proba(X_test_s)[:, 1]

    return {
        "AUROC": round(roc_auc_score(y_test, y_prob), 4),
        "AUPRC": round(average_precision_score(y_test, y_prob), 4),
        "Brier": round(brier_score_loss(y_test, y_prob), 4),
    }


def main() -> None:
    use_local_tracking("readmission")

    df = load_clean()
    df_train, df_test = patient_level_split(df, "patient_nbr", test_size=0.2)
    assert_no_patient_leakage(df_train, df_test, "patient_nbr")

    X_train, y_train, _ = build_features(df_train)
    X_test, y_test, _ = build_features(df_test)

    baseline_metrics = train_baseline(df_train, df_test)
    print("Baseline (logistic regression):", baseline_metrics)

    pos = y_train.sum()
    neg = len(y_train) - pos
    scale_pos_weight = neg / pos

    with mlflow.start_run(run_name=MODEL_VERSION):
        mlflow.log_param("model_type", "LightGBM")
        mlflow.log_param("scale_pos_weight", scale_pos_weight)
        mlflow.log_param("n_train", len(X_train))
        mlflow.log_param("n_test", len(X_test))

        base_model = lgb.LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            num_leaves=31,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            verbosity=-1,
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
        save_reliability_plot(diagram, CALIBRATION_PLOT_PATH, "30-day readmission calibration")
        mlflow.log_artifact(str(CALIBRATION_PLOT_PATH))

        # Fairness: subgroup AUROC/Brier gaps across race, gender, age band.
        reports = {
            "race": subgroup_report(y_test.values, y_prob, df_test["race"].astype(str).values),
            "gender": subgroup_report(y_test.values, y_prob, df_test["gender"].astype(str).values),
            "age band": subgroup_report(y_test.values, y_prob, df_test["age"].astype(str).values),
        }
        for name, rep in reports.items():
            gaps_str = ", ".join(f"max {m} gap={g:.4f}" for m, g in rep.metric_gaps.items())
            print(f"Fairness [{name}]: {gaps_str}")
            for m, g in rep.metric_gaps.items():
                mlflow.log_metric(f"fairness_{name.replace(' ', '_')}_{m}_gap", g)

        # SHAP: global + a couple of example per-patient explanations, using an
        # uncalibrated model of identical hyperparameters (TreeExplainer needs
        # direct tree access; calibration wraps the model in a CV ensemble).
        shap_values = tree_shap_values(base_model, X_test)
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        top_global = sorted(zip(X_test.columns, mean_abs_shap, strict=True), key=lambda t: -t[1])[:10]
        print("Top global SHAP drivers:")
        for name, val in top_global:
            print(f"  {name}: {val:.4f}")

        write_model_card(
            MODEL_CARD_PATH,
            title="30-day readmission risk",
            intended_use=(
                "Decision support flagging patients at elevated risk of readmission within 30 days "
                "of discharge, for care-team follow-up prioritisation. Not a diagnosis, not a "
                "triage tool, and never shown to patients (SPEC clinical safety rule 4)."
            ),
            data_provenance=(
                "UCI Diabetes 130-US Hospitals (1999-2008), 101,766 real de-identified inpatient "
                f"encounters, {df['patient_nbr'].nunique()} unique patients after dropping expired/"
                "hospice discharges. US hospitals, not UAE -- this demonstrates method, not "
                "UAE clinical performance (see README honesty note)."
            ),
            baseline_name="Logistic regression (prior admissions + LOS)",
            baseline_metrics=baseline_metrics,
            main_metrics=main_metrics,
            subgroup_reports=reports,
            limitations=[
                "Trained on US hospital data from 1999-2008; not validated on UAE populations.",
                (
                    "Diagnosis codes are ICD-9 grouped into 9 broad clinical categories, losing "
                    "fine-grained diagnostic detail."
                ),
                "Individual medication columns were not used as features (only medication count).",
                "Not for diagnosis, triage, or any use visible to patients.",
            ],
            model_version=MODEL_VERSION,
            calibration_plot_filename=CALIBRATION_PLOT_PATH.name,
        )
        print(f"Model card written to {MODEL_CARD_PATH}")

        artifact_path = log_model_joblib(calibrated_model, "readmission")
        print(f"Model artifact saved to {artifact_path}")


if __name__ == "__main__":
    main()
