"""Leakage tests against the real datasets (SPEC 6.2 acceptance criteria:
"Patient-level split and leakage tests in CI"). Skipped if the raw CSVs
haven't been downloaded yet (`uv run python ml/data/download.py`)."""

import pytest

from ml.common.splits import assert_no_patient_leakage, patient_level_split
from ml.los import features as los_features
from ml.noshow import features as noshow_features
from ml.readmission import features as readmission_features

readmission_data = pytest.mark.skipif(
    not readmission_features.RAW_PATH.exists(), reason="diabetic_data.csv not downloaded"
)
noshow_data = pytest.mark.skipif(
    not noshow_features.RAW_PATH.exists(), reason="noshow_appointments.csv not downloaded"
)


@readmission_data
def test_readmission_split_has_no_patient_leakage():
    df = readmission_features.load_clean()
    train, test = patient_level_split(df, "patient_nbr", test_size=0.2)
    assert_no_patient_leakage(train, test, "patient_nbr")
    assert len(train) > 0 and len(test) > 0


@readmission_data
def test_readmission_more_encounters_than_patients():
    # Confirms the dataset genuinely needs a patient-level split (some
    # patients have multiple encounters) -- otherwise this test would be
    # trivially satisfied by any split.
    df = readmission_features.load_clean()
    assert df["patient_nbr"].nunique() < len(df)


@readmission_data
def test_los_split_has_no_patient_leakage():
    df = los_features.load_clean()
    train, test = patient_level_split(df, "patient_nbr", test_size=0.2)
    assert_no_patient_leakage(train, test, "patient_nbr")


@readmission_data
def test_los_excludes_discharge_time_features():
    # SPEC 6.2: LOS must use admission-time features only.
    leaky_columns = {"discharge_disposition_id", "num_lab_procedures", "num_procedures", "num_medications"}
    assert leaky_columns.isdisjoint(los_features.FEATURE_COLUMNS)


@noshow_data
def test_noshow_split_has_no_patient_leakage():
    df = noshow_features.load_clean()
    train, test = patient_level_split(df, "PatientId", test_size=0.2)
    assert_no_patient_leakage(train, test, "PatientId")


@noshow_data
def test_noshow_lead_time_is_non_negative():
    df = noshow_features.load_clean()
    assert (df["lead_time_days"] >= 0).all()
