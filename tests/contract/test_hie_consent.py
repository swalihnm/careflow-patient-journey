"""SPEC 5 acceptance criteria: HIE sharing fails without a valid Consent (tested).

Runs the HIE FastAPI app in-process (TestClient) against the real, running
HAPI FHIR server -- no separate hie container needed for this test.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from hie import consent as hie_consent
from hie.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _create_patient(fhir_base_url: str, patient_id: str) -> None:
    patient = {
        "resourceType": "Patient",
        "id": patient_id,
        "name": [{"use": "official", "given": ["Consent"], "family": "TestSubject"}],
        "gender": "male",
    }
    with httpx.Client(timeout=10.0) as c:
        resp = c.put(f"{fhir_base_url}/Patient/{patient_id}", json=patient)
        resp.raise_for_status()


def test_share_denied_without_consent(client, fhir_base_url, latest_audit_row):
    patient_id = "hie-test-no-consent"
    _create_patient(fhir_base_url, patient_id)

    resp = client.post(
        "/share",
        json={
            "patient_id": patient_id,
            "from_org": "org-downtown",
            "to_org": "org-marina",
            "document_type": "discharge-summary",
        },
    )
    assert resp.status_code == 403

    *_rest, result, reason = latest_audit_row()
    assert result == "deny"
    assert "consent" in reason.lower()

    docs = client.get("/documents", params={"patient_id": patient_id}).json()
    assert docs == []


def test_share_allowed_with_consent(client, fhir_base_url, latest_audit_row):
    patient_id = "hie-test-with-consent"
    _create_patient(fhir_base_url, patient_id)

    consent_resource = hie_consent.build_consent_resource("hie-test-consent-1", patient_id)
    with httpx.Client(timeout=10.0) as c:
        resp = c.put(f"{fhir_base_url}/Consent/hie-test-consent-1", json=consent_resource)
        resp.raise_for_status()

    resp = client.post(
        "/share",
        json={
            "patient_id": patient_id,
            "from_org": "org-downtown",
            "to_org": "org-marina",
            "document_type": "discharge-summary",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["shared"] is True

    *_rest, result, _reason = latest_audit_row()
    assert result == "allow"

    docs = client.get("/documents", params={"patient_id": patient_id}).json()
    assert any(d["document_type"] == "discharge-summary" for d in docs)
