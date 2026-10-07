"""Patient-level train/test splitting, shared by every model.

SPEC 6.2: "split by patient, never by encounter, so the same patient never
appears in train and test." A naive row-level split would leak information
(a patient's later encounter influencing prediction on their earlier one via
shared model capacity), so every model in this repo must use this, not
sklearn's plain train_test_split.
"""

import numpy as np
import pandas as pd


def patient_level_split(
    df: pd.DataFrame,
    patient_col: str,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Splits `df` into (train, test) such that no `patient_col` value appears
    in both halves. Returns copies to avoid downstream SettingWithCopy surprises.
    """
    # np.asarray(..., dtype=object): pandas may back this column with an Arrow
    # string array (e.g. after `.astype(str)`), which numpy's shuffle warns it
    # can't guarantee correct in-place behavior for.
    patients = np.asarray(df[patient_col].unique(), dtype=object)
    rng = np.random.default_rng(random_state)
    shuffled = patients.copy()
    rng.shuffle(shuffled)

    n_test = max(1, int(len(shuffled) * test_size))
    test_patients = set(shuffled[:n_test])

    test_mask = df[patient_col].isin(test_patients)
    train_df = df.loc[~test_mask].copy()
    test_df = df.loc[test_mask].copy()
    return train_df, test_df


def assert_no_patient_leakage(train_df: pd.DataFrame, test_df: pd.DataFrame, patient_col: str) -> None:
    overlap = set(train_df[patient_col]) & set(test_df[patient_col])
    if overlap:
        raise AssertionError(f"{len(overlap)} patient(s) leaked across train/test: {list(overlap)[:5]}...")
