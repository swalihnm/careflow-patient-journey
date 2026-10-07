"""Pure-logic tests for ml/features_fhir.py's FHIR-to-feature mapping (no FHIR
server needed -- see tests/contract/test_features_fhir.py for the live,
end-to-end version)."""

from ml.features_fhir import _map_fhir_gender, map_readmission_features


def test_map_fhir_gender_matches_training_data_casing():
    # Regression test for a real bug: the UCI training data's `gender` column
    # is "Male"/"Female"/"Unknown/Invalid" (capitalized), but FHIR's
    # Patient.gender is lowercase ("male"/"female"). Passing the raw FHIR
    # value straight through silently never matched a trained category --
    # LightGBM treated it as missing rather than erroring, so this had no
    # visible symptom until checked directly.
    assert _map_fhir_gender("male") == "Male"
    assert _map_fhir_gender("female") == "Female"
    assert _map_fhir_gender("other") == "Unknown/Invalid"
    assert _map_fhir_gender(None) == "Unknown/Invalid"


def test_map_readmission_features_gender_is_capitalized_and_not_defaulted():
    context = {
        "patient": {"birthDate": "1970-01-01", "gender": "female"},
        "conditions": [],
        "encounters": [],
        "medications": [],
    }
    result = map_readmission_features(context)
    assert result.row["gender"] == "Female"
    assert "gender" not in result.defaulted_fields


def test_map_readmission_features_unknown_gender_is_defaulted():
    context = {
        "patient": {"birthDate": "1970-01-01"},  # no gender field at all
        "conditions": [],
        "encounters": [],
        "medications": [],
    }
    result = map_readmission_features(context)
    assert result.row["gender"] == "Unknown/Invalid"
    assert "gender" in result.defaulted_fields
