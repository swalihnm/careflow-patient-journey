"""FHIR Consent check for the HIE mock.

Inspired by how a real health information exchange (e.g. Dubai's NABIDH) gates
sharing on consent, without claiming to replicate it — see SPEC section 5.
"""

import httpx

CONSENT_CATEGORY_SYSTEM = "http://careflow.example/consent-category"
HIE_SHARE_CATEGORY = "hie-share"


def build_consent_resource(
    consent_id: str,
    patient_id: str,
    status: str = "active",
    category_code: str = HIE_SHARE_CATEGORY,
) -> dict:
    return {
        "resourceType": "Consent",
        "id": consent_id,
        "status": status,
        "scope": {
            "coding": [
                {"system": "http://terminology.hl7.org/CodeSystem/consentscope", "code": "patient-privacy"}
            ]
        },
        "category": [{"coding": [{"system": CONSENT_CATEGORY_SYSTEM, "code": category_code}]}],
        "patient": {"reference": f"Patient/{patient_id}"},
    }


def has_active_consent(fhir_base_url: str, patient_id: str) -> bool:
    """An active Consent for this patient, tagged for HIE sharing, must exist."""
    params = {"patient": f"Patient/{patient_id}", "status": "active"}
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{fhir_base_url.rstrip('/')}/Consent", params=params)
    resp.raise_for_status()
    bundle = resp.json()

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        for category in resource.get("category", []):
            for coding in category.get("coding", []):
                if coding.get("system") == CONSENT_CATEGORY_SYSTEM and coding.get("code") == HIE_SHARE_CATEGORY:
                    return True
    return False
