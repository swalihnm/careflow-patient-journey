"""CareFlow API (SPEC 9). Runs the real app in-process (TestClient triggers
the real lifespan: schema bootstrap, specmcp server, compiled graph with a
Postgres checkpointer) against the live FHIR/Postgres services.
"""

import httpx
import pytest
from api.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def patient_id(fhir_base_url):
    pid = "test-patient-api"
    patient = {
        "resourceType": "Patient",
        "id": pid,
        "name": [{"use": "official", "given": ["Api"], "family": "TestSubject"}],
        "gender": "female",
        "birthDate": "1990-01-01",
    }
    with httpx.Client(timeout=10.0) as c:
        resp = c.put(f"{fhir_base_url}/Patient/{pid}", json=patient)
        resp.raise_for_status()
    return pid


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_default_role_is_patient_and_cannot_see_risk_scores(client):
    resp = client.get("/v1/patients")
    assert resp.status_code == 403


def test_clinician_can_list_patients(client):
    resp = client.get("/v1/patients", headers={"X-Role": "clinician"})
    assert resp.status_code == 200
    assert "patients" in resp.json()


def test_unknown_role_is_rejected(client):
    resp = client.get("/v1/patients", headers={"X-Role": "supervillain"})
    assert resp.status_code == 400


def test_chat_clinic_info(client, patient_id):
    resp = client.post("/v1/chat", json={"patient_id": patient_id, "message": "What are your opening hours?"})
    assert resp.status_code == 200
    body = resp.text
    assert "data: " in body
    assert "clinic" in body.lower() or "9:00" in body


def test_chat_escalation_is_auditable(client, patient_id):
    resp = client.post(
        "/v1/chat", json={"patient_id": patient_id, "message": "I have severe chest pain right now"}
    )
    assert resp.status_code == 200
    assert '"escalated": true' in resp.text.lower() or '"escalated":true' in resp.text.lower()

    audit_resp = client.get("/v1/escalations", headers={"X-Role": "nurse"})
    assert audit_resp.status_code == 200
    escalations = audit_resp.json()["escalations"]
    assert any(e["patient_id"] == patient_id for e in escalations)


def test_consent_grant_and_withdraw(client, patient_id, fhir_base_url):
    grant = client.post("/v1/consent", json={"patient_id": patient_id, "category": "hie-share", "active": True})
    assert grant.status_code == 200
    assert grant.json()["status"] == "active"

    with httpx.Client(timeout=10.0) as c:
        resp = c.get(f"{fhir_base_url}/Consent/consent-{patient_id}-hie-share")
    assert resp.json()["status"] == "active"

    withdraw = client.post("/v1/consent", json={"patient_id": patient_id, "category": "hie-share", "active": False})
    assert withdraw.status_code == 200
    assert withdraw.json()["status"] == "inactive"


def test_audit_endpoint_shows_chain_status(client):
    resp = client.get("/v1/audit", headers={"X-Role": "auditor"}, params={"limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert "chain_status" in body
    assert body["chain_status"]["ok"] is True
    # auditor role sees masked identifiers
    for event in body["events"]:
        assert event["actor"] == "***MASKED***"


def test_audit_forbidden_for_patient_role(client):
    resp = client.get("/v1/audit")
    assert resp.status_code == 403


def test_qa_overview_requires_admin_or_clinician(client):
    forbidden = client.get("/v1/qa/overview")
    assert forbidden.status_code == 403

    allowed = client.get("/v1/qa/overview", headers={"X-Role": "admin"})
    assert allowed.status_code == 200
    body = allowed.json()
    assert "total_scored" in body
    assert "recent_eval_runs" in body  # SPEC 11: nightly eval run history


def test_experiment_report_unknown_id_is_404(client):
    resp = client.get("/v1/experiments/does-not-exist/report", headers={"X-Role": "admin"})
    assert resp.status_code == 404


def test_risk_score_readmission_live(client, patient_id):
    resp = client.post(
        "/v1/risk/readmission/score", params={"patient_id": patient_id}, headers={"X-Role": "system"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert 0.0 <= body["probability"] <= 1.0
    assert len(body["drivers"]) == 5


def test_risk_score_los_live(client, patient_id):
    resp = client.post("/v1/risk/los/score", params={"patient_id": patient_id}, headers={"X-Role": "system"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["point_days"] > 0
    assert body["interval_80_low_days"] <= body["point_days"] <= body["interval_80_high_days"]
    assert len(body["drivers"]) == 5


def test_risk_score_noshow_requires_appointment_id(client, patient_id):
    resp = client.post("/v1/risk/noshow/score", params={"patient_id": patient_id}, headers={"X-Role": "system"})
    assert resp.status_code == 400


def test_risk_score_noshow_live(client, patient_id, fhir_base_url):
    appointment_id = "test-appointment-api-noshow"
    appointment = {
        "resourceType": "Appointment",
        "id": appointment_id,
        "status": "booked",
        "start": "2026-12-01T09:00:00+00:00",
        "end": "2026-12-01T10:00:00+00:00",
        "participant": [{"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"}],
    }
    with httpx.Client(timeout=10.0) as c:
        resp = c.put(f"{fhir_base_url}/Appointment/{appointment_id}", json=appointment)
        resp.raise_for_status()

    resp = client.post(
        "/v1/risk/noshow/score",
        params={"patient_id": patient_id, "appointment_id": appointment_id},
        headers={"X-Role": "system"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert 0.0 <= body["probability"] <= 1.0
    assert len(body["drivers"]) == 5


def test_risk_score_unknown_model_returns_404(client, patient_id):
    resp = client.post("/v1/risk/not-a-model/score", params={"patient_id": patient_id}, headers={"X-Role": "system"})
    assert resp.status_code == 404


_DRAFT_CLAIM_BODY = {
    "claim_id": "api-test-claim-1",
    "patient_id": "api-test-patient-1",
    "practitioner_id": "api-test-practitioner-1",
    "plan_name": "Gulf Horizon Standard",
    "policy_start_date": "2024-01-01",
    "service_date": "2024-06-01",
    "pre_authorization_obtained": False,
    "lines": [
        {
            "line_id": "L1",
            "service_type": "cosmetic_procedure",
            "diagnosis_code": "Z41.1",
            "procedure_code": "PRC0001",
            "amount_aed": 500.0,
            "encounter_documentation": "Elective cosmetic consultation.",
        }
    ],
}


def test_claims_precheck_requires_admin(client):
    resp = client.post("/v1/claims/precheck", json=_DRAFT_CLAIM_BODY, headers={"X-Role": "clinician"})
    assert resp.status_code == 403


def test_claims_precheck_flags_excluded_cosmetic_service(client):
    resp = client.post("/v1/claims/precheck", json=_DRAFT_CLAIM_BODY, headers={"X-Role": "admin"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["clean"] is False
    assert any(f["flag_type"] == "cosmetic_excluded" for f in body["flags"])
    assert all(f["reason"] and f["evidence"] for f in body["flags"])


def test_claims_decision_roundtrip(client):
    resp = client.post(
        "/v1/claims/decisions",
        json={
            "claim_id": "api-test-claim-1",
            "flag_type": "cosmetic_excluded",
            "decision": "dismiss",
            "coder_id": "api-test-coder",
            "note": "Patient will self-pay.",
        },
        headers={"X-Role": "admin"},
    )
    assert resp.status_code == 200

    resp = client.get("/v1/claims/decisions", headers={"X-Role": "admin"})
    assert resp.status_code == 200
    decisions = resp.json()["decisions"]
    assert any(d["claim_id"] == "api-test-claim-1" and d["decision"] == "dismiss" for d in decisions)
