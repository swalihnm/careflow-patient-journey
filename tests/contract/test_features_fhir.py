"""Live FHIR -> feature mapping -> model score -> RiskAssessment write-back
(SPEC 6.3). Needs a trained model artifact (`uv run python -m ml.readmission.train`)
and a running FHIR server; creates its own throwaway patient rather than
depending on seed data being loaded."""

import httpx
import pytest

from ml.features_fhir import (
    ARTIFACTS_DIR,
    LOS_INTERVAL_EXTENSION_URL,
    LOS_POINT_EXTENSION_URL,
    build_los_risk_assessment,
    build_risk_assessment,
    score_los,
    score_noshow,
    score_readmission,
    write_risk_assessment,
)

pytestmark = pytest.mark.skipif(
    not (ARTIFACTS_DIR / "readmission.joblib").exists(),
    reason="readmission model not trained yet (uv run python -m ml.readmission.train)",
)

TEST_PATIENT_ID = "test-patient-scoring"


@pytest.fixture(scope="module")
def patient_id(fhir_base_url):
    patient = {
        "resourceType": "Patient",
        "id": TEST_PATIENT_ID,
        "name": [{"use": "official", "given": ["Scoring"], "family": "TestSubject"}],
        "gender": "female",
        "birthDate": "1975-06-01",
    }
    encounter = {
        "resourceType": "Encounter",
        "id": "test-encounter-scoring-1",
        "status": "finished",
        "class": {"code": "IMP"},
        "subject": {"reference": f"Patient/{TEST_PATIENT_ID}"},
    }
    condition = {
        "resourceType": "Condition",
        "id": "test-condition-scoring-1",
        "subject": {"reference": f"Patient/{TEST_PATIENT_ID}"},
        "code": {"text": "Type 2 diabetes mellitus"},
    }
    with httpx.Client(timeout=10.0) as client:
        for resource in (patient, encounter, condition):
            resp = client.put(f"{fhir_base_url}/{resource['resourceType']}/{resource['id']}", json=resource)
            resp.raise_for_status()
    return TEST_PATIENT_ID


def test_score_readmission_from_live_fhir_data(fhir_base_url, patient_id):
    result = score_readmission(fhir_base_url, patient_id)

    assert result["model"] == "readmission"
    assert 0.0 <= result["probability"] <= 1.0
    assert len(result["drivers"]) == 5
    assert 0.0 <= result["confidence"] <= 1.0
    # This patient's Condition text says "diabetes" -- the keyword mapper
    # should catch that and NOT default diag_1_group.
    assert "diag_1_group" not in result["defaulted_fields"]


def test_risk_assessment_written_back_to_fhir(fhir_base_url, patient_id):
    result = score_readmission(fhir_base_url, patient_id)
    resource = build_risk_assessment(patient_id, result, "30-day readmission")
    write_risk_assessment(fhir_base_url, patient_id, resource)

    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{fhir_base_url}/RiskAssessment/{resource['id']}")
    resp.raise_for_status()
    fetched = resp.json()

    assert fetched["resourceType"] == "RiskAssessment"
    assert fetched["subject"]["reference"] == f"Patient/{patient_id}"
    assert fetched["prediction"][0]["probabilityDecimal"] == result["probability"]
    assert fetched["extension"][0]["valueDecimal"] == result["confidence"]


@pytest.mark.skipif(not (ARTIFACTS_DIR / "los.joblib").exists(), reason="los model not trained yet (uv run python -m ml.los.train)")
def test_score_los_from_live_fhir_data(fhir_base_url, patient_id):
    result = score_los(fhir_base_url, patient_id)

    assert result["model"] == "los"
    assert result["point_days"] > 0
    assert result["interval_80_low_days"] <= result["point_days"] <= result["interval_80_high_days"]
    assert len(result["drivers"]) == 5
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.skipif(not (ARTIFACTS_DIR / "los.joblib").exists(), reason="los model not trained yet (uv run python -m ml.los.train)")
def test_los_risk_assessment_written_back_to_fhir(fhir_base_url, patient_id):
    result = score_los(fhir_base_url, patient_id)
    resource = build_los_risk_assessment(patient_id, result)
    write_risk_assessment(fhir_base_url, patient_id, resource)

    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{fhir_base_url}/RiskAssessment/{resource['id']}")
    resp.raise_for_status()
    fetched = resp.json()

    assert fetched["resourceType"] == "RiskAssessment"
    # LOS isn't a probability -- carried as extensions instead (see
    # build_los_risk_assessment's docstring).
    assert "probabilityDecimal" not in fetched["prediction"][0]
    extensions_by_url = {e["url"]: e for e in fetched["extension"]}
    assert extensions_by_url[LOS_POINT_EXTENSION_URL]["valueDecimal"] == result["point_days"]
    assert extensions_by_url[LOS_INTERVAL_EXTENSION_URL]["valueRange"]["low"]["value"] == result["interval_80_low_days"]


@pytest.mark.skipif(not (ARTIFACTS_DIR / "noshow.joblib").exists(), reason="noshow model not trained yet (uv run python -m ml.noshow.train)")
def test_score_noshow_from_live_fhir_data(fhir_base_url, patient_id):
    appointment_id = "test-appointment-noshow-scoring"
    appointment = {
        "resourceType": "Appointment",
        "id": appointment_id,
        "status": "booked",
        "start": "2026-11-15T09:00:00+00:00",
        "end": "2026-11-15T10:00:00+00:00",
        "participant": [{"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"}],
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.put(f"{fhir_base_url}/Appointment/{appointment_id}", json=appointment)
        resp.raise_for_status()

    result = score_noshow(fhir_base_url, patient_id, appointment_id)

    assert result["model"] == "noshow"
    assert 0.0 <= result["probability"] <= 1.0
    assert len(result["drivers"]) == 5
    assert 0.0 <= result["confidence"] <= 1.0
    # No UAE equivalent for the training data's Brazilian neighbourhoods --
    # always defaulted, documented in map_noshow_features.
    assert "Neighbourhood" in result["defaulted_fields"]
