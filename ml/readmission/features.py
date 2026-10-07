"""Feature engineering for the 30-day readmission model (SPEC 6.1, 6.3)."""

from pathlib import Path

import pandas as pd

from ml.common.icd9_groups import group_icd9

RAW_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "diabetic_data.csv"

# Discharge dispositions meaning the patient died or entered hospice: cannot be
# readmitted, so these encounters are dropped -- standard practice for this
# dataset, documented in the paper it comes from (Strack et al. 2014).
EXPIRED_OR_HOSPICE_DISPOSITIONS = {11, 13, 14, 19, 20, 21}

AGE_MIDPOINTS = {
    "[0-10)": 5, "[10-20)": 15, "[20-30)": 25, "[30-40)": 35, "[40-50)": 45,
    "[50-60)": 55, "[60-70)": 65, "[70-80)": 75, "[80-90)": 85, "[90-100)": 95,
}

CATEGORICAL_COLUMNS = [
    "race", "gender", "admission_type_id", "discharge_disposition_id",
    "admission_source_id", "diag_1_group", "diag_2_group", "diag_3_group",
    "max_glu_serum", "A1Cresult", "change", "diabetesMed",
]

NUMERIC_COLUMNS = [
    "age_midpoint", "time_in_hospital", "num_lab_procedures", "num_procedures",
    "num_medications", "number_outpatient", "number_emergency",
    "number_inpatient", "number_diagnoses",
]

FEATURE_COLUMNS = NUMERIC_COLUMNS + CATEGORICAL_COLUMNS

BASELINE_COLUMNS = ["number_inpatient", "time_in_hospital"]


def load_clean(raw_path: Path = RAW_PATH) -> pd.DataFrame:
    df = pd.read_csv(raw_path, na_values=["?"], low_memory=False)
    df = df[~df["discharge_disposition_id"].isin(EXPIRED_OR_HOSPICE_DISPOSITIONS)].copy()

    df["age_midpoint"] = df["age"].map(AGE_MIDPOINTS)
    df["diag_1_group"] = df["diag_1"].map(group_icd9)
    df["diag_2_group"] = df["diag_2"].map(group_icd9)
    df["diag_3_group"] = df["diag_3"].map(group_icd9)

    df["readmitted_30"] = (df["readmitted"] == "<30").astype(int)

    for col in CATEGORICAL_COLUMNS:
        df[col] = df[col].astype("category")

    return df


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Returns (X, y, patient_id) for the main model."""
    X = df[FEATURE_COLUMNS].copy()
    y = df["readmitted_30"].copy()
    patient_id = df["patient_nbr"].copy()
    return X, y, patient_id
