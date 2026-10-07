"""Feature engineering for the no-show model (SPEC 6.1)."""

from pathlib import Path

import pandas as pd

RAW_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "noshow_appointments.csv"

CATEGORICAL_COLUMNS = ["Gender", "Neighbourhood", "appointment_weekday"]
NUMERIC_COLUMNS = [
    "lead_time_days", "Age", "Scholarship", "Hipertension", "Diabetes",
    "Alcoholism", "Handcap", "SMS_received",
]
FEATURE_COLUMNS = NUMERIC_COLUMNS + CATEGORICAL_COLUMNS

BASELINE_COLUMN = "lead_time_days"


def load_clean(raw_path: Path = RAW_PATH) -> pd.DataFrame:
    df = pd.read_csv(raw_path)
    df["PatientId"] = df["PatientId"].astype("int64").astype(str)

    df["ScheduledDay"] = pd.to_datetime(df["ScheduledDay"])
    df["AppointmentDay"] = pd.to_datetime(df["AppointmentDay"])

    # lead time in whole days; clip negatives (a handful of rows have a
    # scheduling timestamp after midnight on the appointment day itself --
    # a data-entry quirk in the source dataset, not a real negative lead time)
    lead = (df["AppointmentDay"].dt.normalize() - df["ScheduledDay"].dt.normalize()).dt.days
    df["lead_time_days"] = lead.clip(lower=0)

    df["appointment_weekday"] = df["AppointmentDay"].dt.day_name()

    # A small number of rows have Age < 0, a known data-quality issue in this
    # dataset (documented on its Kaggle page) -- dropped, not imputed, since
    # there's no principled value to impute a negative age to.
    df = df[df["Age"] >= 0].copy()

    df["no_show"] = (df["No-show"] == "Yes").astype(int)

    for col in CATEGORICAL_COLUMNS:
        df[col] = df[col].astype("category")

    return df


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    X = df[FEATURE_COLUMNS].copy()
    y = df["no_show"].copy()
    patient_id = df["PatientId"].copy()
    return X, y, patient_id
