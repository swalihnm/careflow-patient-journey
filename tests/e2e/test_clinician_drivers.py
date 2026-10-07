"""SPEC 11 acceptance criterion: "... clinician viewing drivers ...".

Scores a fresh patient live (via the real readmission model, same path
ml/features_fhir.py / POST /v1/risk/readmission/score uses) so this test
doesn't depend on `make seed` having been run, then checks the care-team
dashboard's patient-detail page renders that score's driver bars.
"""

import httpx

from tests.e2e.conftest import API_BASE_URL, CARE_WEB_URL, set_care_web_role


def test_clinician_can_view_risk_drivers_for_a_patient(page, patient_id):
    patient = {
        "resourceType": "Patient",
        "id": patient_id,
        "name": [{"use": "official", "given": ["E2E"], "family": "DriversTest"}],
        "gender": "female",
        "birthDate": "1980-01-01",
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.put(f"http://localhost:8210/fhir/Patient/{patient_id}", json=patient)
        resp.raise_for_status()

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{API_BASE_URL}/v1/risk/readmission/score",
            params={"patient_id": patient_id},
            headers={"X-Role": "system"},
        )
        resp.raise_for_status()

    page.goto(f"{CARE_WEB_URL}/patients/{patient_id}")
    set_care_web_role(page, "clinician")
    page.wait_for_timeout(1_000)

    assert page.locator(".driver-bar-row").count() == 5, "expected the standard top-5 SHAP drivers rendered as bars"
    assert "readmission-v1" in page.locator("main").inner_text()
