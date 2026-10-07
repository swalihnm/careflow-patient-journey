"""Patient-level split correctness (SPEC 6.2 leakage control) and the ICD-9
grouping used by the readmission/LOS models."""

import pandas as pd
import pytest

from ml.common.icd9_groups import group_icd9
from ml.common.splits import assert_no_patient_leakage, patient_level_split


def _synthetic_encounters(n_patients: int = 50, encounters_per_patient: int = 3) -> pd.DataFrame:
    rows = []
    for pid in range(n_patients):
        for _ in range(encounters_per_patient):
            rows.append({"patient_id": pid, "value": pid * 10})
    return pd.DataFrame(rows)


def test_patient_level_split_has_no_overlap():
    df = _synthetic_encounters()
    train, test = patient_level_split(df, "patient_id", test_size=0.2, random_state=1)
    assert_no_patient_leakage(train, test, "patient_id")  # must not raise


def test_patient_level_split_keeps_all_rows():
    df = _synthetic_encounters()
    train, test = patient_level_split(df, "patient_id", test_size=0.2, random_state=1)
    assert len(train) + len(test) == len(df)


def test_patient_level_split_roughly_matches_test_size():
    df = _synthetic_encounters(n_patients=1000, encounters_per_patient=1)
    _train, test = patient_level_split(df, "patient_id", test_size=0.2, random_state=1)
    assert 0.15 < len(test) / len(df) < 0.25


def test_assert_no_patient_leakage_raises_on_overlap():
    df = pd.DataFrame({"patient_id": [1, 1, 2], "value": [1, 2, 3]})
    with pytest.raises(AssertionError):
        assert_no_patient_leakage(df, df, "patient_id")  # same df on both sides = leakage


@pytest.mark.parametrize(
    "code,expected",
    [
        ("250.83", "Diabetes"),
        ("250", "Diabetes"),
        ("410", "Circulatory"),
        ("786", "Respiratory"),
        ("520", "Digestive"),
        ("820", "Injury"),
        ("715", "Musculoskeletal"),
        ("599", "Genitourinary"),
        ("150", "Neoplasms"),
        ("V27", "Other"),
        ("E888", "Other"),
        (None, "Other"),
        ("?", "Other"),
    ],
)
def test_group_icd9(code, expected):
    assert group_icd9(code) == expected
