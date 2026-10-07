"""Groups the UCI Diabetes 130 dataset's ICD-9 diagnosis codes into clinical
categories (SPEC 3: "the UCI data uses ICD-9, so group diagnoses into clinical
categories for the model and document the mapping").

The grouping follows the scheme from the dataset's originating paper (Strack
et al. 2014, "Impact of HbA1c Measurement on Hospital Readmission Rates"),
which is also the grouping most tutorials on this dataset replicate:
Circulatory, Respiratory, Digestive, Diabetes, Injury, Musculoskeletal,
Genitourinary, Neoplasms, Other.
"""

CATEGORIES = [
    "Circulatory",
    "Respiratory",
    "Digestive",
    "Diabetes",
    "Injury",
    "Musculoskeletal",
    "Genitourinary",
    "Neoplasms",
    "Other",
]


def group_icd9(code: str | float | None) -> str:
    """`code` is the raw string from diag_1/diag_2/diag_3 (e.g. "250.83", "V27",
    "786", or NaN/"?" for missing)."""
    if code is None:
        return "Other"
    code_str = str(code).strip()
    if code_str in ("", "?", "nan", "NaN"):
        return "Other"

    if code_str.startswith("250"):
        return "Diabetes"
    if code_str.startswith(("V", "E")):
        return "Other"

    try:
        numeric = float(code_str)
    except ValueError:
        return "Other"

    if 390 <= numeric <= 459 or numeric == 785:
        return "Circulatory"
    if 460 <= numeric <= 519 or numeric == 786:
        return "Respiratory"
    if 520 <= numeric <= 579 or numeric == 787:
        return "Digestive"
    if 800 <= numeric <= 999:
        return "Injury"
    if 710 <= numeric <= 739:
        return "Musculoskeletal"
    if 580 <= numeric <= 629 or numeric == 788:
        return "Genitourinary"
    if 140 <= numeric <= 239:
        return "Neoplasms"
    return "Other"
