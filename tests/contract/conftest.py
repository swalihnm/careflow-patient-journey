"""Contract tests exercise specmcp/HIE against a real, running HAPI FHIR
server. Run `make up` (docker compose) before running these -- they are not
mocked and will fail with connection errors if the server isn't up."""

import os

import httpx
import pytest
from trustcore import db as trustcore_db

FHIR_BASE_URL = os.environ["CAREFLOW_FHIR_BASE_URL"]

TEST_PATIENT_ID = "test-patient-1"


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    trustcore_db.ensure_schema()


@pytest.fixture(scope="session")
def fhir_base_url():
    return FHIR_BASE_URL


@pytest.fixture(scope="session")
def test_patient_id(fhir_base_url):
    patient = {
        "resourceType": "Patient",
        "id": TEST_PATIENT_ID,
        "name": [{"use": "official", "given": ["Test"], "family": "Patient"}],
        "gender": "female",
        "identifier": [{"system": "http://careflow.example/test-id", "value": "abc123"}],
        "telecom": [{"system": "phone", "value": "+971500000000"}],
    }
    condition = {
        "resourceType": "Condition",
        "id": "test-condition-1",
        "subject": {"reference": f"Patient/{TEST_PATIENT_ID}"},
        "code": {"text": "Test condition, not a real diagnosis"},
    }
    coverage = {
        "resourceType": "Coverage",
        "id": "test-coverage-1",
        "status": "active",
        "beneficiary": {"reference": f"Patient/{TEST_PATIENT_ID}"},
        "payor": [{"display": "Test Payer"}],
    }
    with httpx.Client(timeout=10.0) as client:
        for resource in (patient, condition, coverage):
            resp = client.put(
                f"{fhir_base_url}/{resource['resourceType']}/{resource['id']}", json=resource
            )
            resp.raise_for_status()
    return TEST_PATIENT_ID


@pytest.fixture
def latest_audit_row():
    """Returns a zero-arg callable so tests can fetch it *after* triggering
    the action they're asserting on, rather than at fixture-setup time."""

    def _fetch() -> tuple:
        conn = trustcore_db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT actor, actor_role, action, resource_type, resource_id, result, reason "
                    "FROM ops.audit_log ORDER BY id DESC LIMIT 1"
                )
                return cur.fetchone()
        finally:
            conn.close()

    return _fetch
