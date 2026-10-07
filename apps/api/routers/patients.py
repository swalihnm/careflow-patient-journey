"""GET /v1/patients, /v1/patients/{id}/summary (SPEC 9).

Role-gated to clinician/nurse/admin: "Patients never see risk scores" is a
non-negotiable clinical safety rule (SPEC rule 4), enforced here, not just
documented -- a `patient`-role request gets a 403, tested in
tests/contract/test_api.py.
"""

import httpx
from fastapi import APIRouter, Depends

from apps.api.dependencies import get_fhir_base_url, require_role

router = APIRouter()

_CLINICAL_ROLES = ("clinician", "nurse", "admin")


def _risk_tier(probability: float) -> str:
    if probability >= 0.5:
        return "high"
    if probability >= 0.2:
        return "medium"
    return "low"


@router.get("/v1/patients")
def list_patients(
    risk_tier: str | None = None,
    _count: int = 50,
    fhir_base_url: str = Depends(get_fhir_base_url),
    role: str = Depends(require_role(*_CLINICAL_ROLES)),
):
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{fhir_base_url}/RiskAssessment", params={"_count": _count, "_sort": "-date"})
    resp.raise_for_status()
    bundle = resp.json()

    rows = []
    for entry in bundle.get("entry", []):
        resource = entry["resource"]
        probability = resource.get("prediction", [{}])[0].get("probabilityDecimal")
        if probability is None:
            continue
        tier = _risk_tier(probability)
        if risk_tier and tier != risk_tier:
            continue
        subject_ref = resource.get("subject", {}).get("reference", "")
        rows.append(
            {
                "patient_id": subject_ref.removeprefix("Patient/"),
                "risk_assessment_id": resource["id"],
                "model": resource.get("method", {}).get("text"),
                "probability": probability,
                "risk_tier": tier,
                "occurrence": resource.get("occurrenceDateTime"),
            }
        )

    rows.sort(key=lambda r: r["probability"], reverse=True)
    return {"patients": rows, "role": role}


@router.get("/v1/patients/{patient_id}/summary")
def patient_summary(
    patient_id: str,
    fhir_base_url: str = Depends(get_fhir_base_url),
    role: str = Depends(require_role(*_CLINICAL_ROLES)),
):
    with httpx.Client(timeout=30.0) as client:
        patient_resp = client.get(f"{fhir_base_url}/Patient/{patient_id}")
        patient_resp.raise_for_status()
        patient = patient_resp.json()

        qr_resp = client.get(
            f"{fhir_base_url}/QuestionnaireResponse", params={"subject": f"Patient/{patient_id}", "_sort": "-authored"}
        )
        qr_resp.raise_for_status()
        questionnaire_responses = qr_resp.json().get("entry", [])

        ra_resp = client.get(f"{fhir_base_url}/RiskAssessment", params={"subject": f"Patient/{patient_id}"})
        ra_resp.raise_for_status()
        risk_assessments = ra_resp.json().get("entry", [])

    names = patient.get("name", [])
    display_name = names[0].get("text") or " ".join(names[0].get("given", []) + [names[0].get("family", "")]) if names else None

    latest_intake = None
    if questionnaire_responses:
        qr = questionnaire_responses[0]["resource"]
        latest_intake = {
            item["linkId"]: item["answer"][0].get("valueString")
            for item in qr.get("item", [])
            if item.get("answer")
        }

    risks = []
    for entry in risk_assessments:
        resource = entry["resource"]
        prediction = resource.get("prediction", [{}])[0]
        risks.append(
            {
                "model": resource.get("method", {}).get("text"),
                "probability": prediction.get("probabilityDecimal"),
                "occurrence": resource.get("occurrenceDateTime"),
                "notes": [n["text"] for n in resource.get("note", [])],
            }
        )

    return {
        "patient_id": patient_id,
        "name": display_name,
        "gender": patient.get("gender"),
        "birth_date": patient.get("birthDate"),
        "latest_intake_summary": latest_intake,
        "risk_assessments": risks,
        "role": role,
    }
