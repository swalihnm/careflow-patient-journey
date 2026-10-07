"""Feature engineering for the length-of-stay model (SPEC 6.1).

Admission-time features only: unlike the readmission model, this must not use
anything only known once the stay is under way or over (discharge
disposition, procedure/lab counts accrued during the stay, secondary
diagnoses added later) -- SPEC 6.2: "for LOS use only features known at
admission." Reuses the same cleaned dataset as the readmission model.
"""

from pathlib import Path

import pandas as pd

from ml.common.icd9_groups import group_icd9
from ml.readmission.features import AGE_MIDPOINTS, EXPIRED_OR_HOSPICE_DISPOSITIONS

RAW_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "diabetic_data.csv"

CATEGORICAL_COLUMNS = [
    "race", "gender", "admission_type_id", "admission_source_id",
    "diag_1_group", "max_glu_serum", "A1Cresult",
]

NUMERIC_COLUMNS = [
    "age_midpoint", "number_outpatient", "number_emergency", "number_inpatient",
]

FEATURE_COLUMNS = NUMERIC_COLUMNS + CATEGORICAL_COLUMNS

TARGET_COLUMN = "time_in_hospital"


def load_clean(raw_path: Path = RAW_PATH) -> pd.DataFrame:
    df = pd.read_csv(raw_path, na_values=["?"], low_memory=False)
    df = df[~df["discharge_disposition_id"].isin(EXPIRED_OR_HOSPICE_DISPOSITIONS)].copy()

    df["age_midpoint"] = df["age"].map(AGE_MIDPOINTS)
    df["diag_1_group"] = df["diag_1"].map(group_icd9)

    for col in CATEGORICAL_COLUMNS:
        df[col] = df[col].astype("category")

    return df


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    X = df[FEATURE_COLUMNS].copy()
    y = df[TARGET_COLUMN].copy()
    patient_id = df["patient_nbr"].copy()
    return X, y, patient_id
