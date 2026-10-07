"""Playwright E2E tests (SPEC 11): drive the two real Next.js apps
(apps/care-web, apps/patient-web) against the real FastAPI backend and the
real assistant graph -- nothing here is mocked.

Needs all three dev servers running first (this repo has no process
manager to start them automatically, same convention as
tests/contract/conftest.py needing `make up` first):

    uv run uvicorn apps.api.main:app --port 8000
    (cd apps/care-web && npm run dev)      # port 3010
    (cd apps/patient-web && npm run dev)   # port 3011

Then: uv run pytest tests/e2e --extra e2e (or just `uv run pytest tests/e2e`
once the e2e extra is synced -- see pyproject.toml).
"""

import uuid

import httpx
import pytest

HAPI_FHIR_URL = "http://localhost:8210/fhir"

CARE_WEB_URL = "http://localhost:3010"
PATIENT_WEB_URL = "http://localhost:3011"
API_BASE_URL = "http://localhost:8000"


def _reachable(url: str) -> bool:
    try:
        httpx.get(url, timeout=2.0)
        return True
    except httpx.HTTPError:
        return False


# Neither CI (.github/workflows/ci.yml) nor a plain local `uv run pytest`
# starts the two Next.js dev servers this whole directory needs -- and
# `pytest-playwright` (the `page` fixture) is only installed via the `e2e`
# extra, not the default set. Skip collecting this directory entirely in
# either case, via `collect_ignore_glob`, rather than letting pytest fail
# on an unresolvable fixture or a connection error. To actually run these:
# start the API (port 8000) and both dev servers (3010, 3011), see this
# file's module docstring, then `uv run pytest tests/e2e`.
try:
    import pytest_playwright  # noqa: F401

    _E2E_INSTALLED = True
except ImportError:
    _E2E_INSTALLED = False

collect_ignore_glob = (
    []
    if _E2E_INSTALLED and all(_reachable(u) for u in (CARE_WEB_URL, PATIENT_WEB_URL, f"{API_BASE_URL}/health"))
    else ["*"]
)


@pytest.fixture
def patient_id() -> str:
    # A fresh id per test -- this session learned the hard way (see
    # PROGRESS.md) that a fixed shared id accumulates cross-run state that
    # makes assertions flaky over time.
    #
    # Must actually exist as a FHIR Patient before use: found via a real
    # bug this fixture used to cause -- POST /v1/consent writes a FHIR
    # Consent referencing Patient/{id}, and HAPI enforces referential
    # integrity (rejects a Consent for a Patient it doesn't have on file
    # with "HAPI-1094: Resource ... not found"), which surfaced in the
    # browser as a misleading CORS error (Starlette's CORS headers aren't
    # attached to a response an unhandled exception produced) rather than
    # the real 500 underneath. Creating the Patient here is what a real
    # registration flow would already have done before a patient ever opens
    # the chat app.
    new_id = f"e2e-patient-{uuid.uuid4().hex[:10]}"
    patient_resource = {
        "resourceType": "Patient",
        "id": new_id,
        "name": [{"use": "official", "given": ["E2E"], "family": "Test"}],
        "gender": "female",
        "birthDate": "1990-01-01",
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.put(f"{HAPI_FHIR_URL}/Patient/{new_id}", json=patient_resource)
        resp.raise_for_status()
    return new_id


def set_care_web_role(page, role: str) -> None:
    page.select_option("#role-select", role)
    page.wait_for_load_state("networkidle")


def complete_patient_gates(page, patient_id: str) -> None:
    """Patient-web's two gate screens: patient id, then consent."""
    page.goto(f"{PATIENT_WEB_URL}/")
    page.fill("input[placeholder]", patient_id)
    page.click("text=Continue")
    page.wait_for_timeout(300)
    page.click("text=I agree, start chatting")
    page.wait_for_timeout(500)
