"""POST /v1/risk/{model}/score (SPEC 9): score one patient, write RiskAssessment.

All three models (readmission, los, noshow) have live FHIR-scoring paths
(ml/features_fhir.py). "noshow" additionally requires an `appointment_id`
query param -- unlike the other two, it scores a specific upcoming
appointment (lead time, weekday), not just the patient's history.
"""

from fastapi import APIRouter, Depends, HTTPException

from apps.api.dependencies import get_fhir_base_url, require_role
from ml.features_fhir import (
    build_los_risk_assessment,
    build_risk_assessment,
    score_los,
    score_noshow,
    score_readmission,
    write_risk_assessment,
)

router = APIRouter()


@router.post("/v1/risk/{model}/score")
def score_patient(
    model: str,
    patient_id: str,
    appointment_id: str | None = None,
    fhir_base_url: str = Depends(get_fhir_base_url),
    role: str = Depends(require_role("system", "clinician", "admin")),
):
    if model == "readmission":
        result = score_readmission(fhir_base_url, patient_id)
        resource = build_risk_assessment(patient_id, result, "30-day readmission")
    elif model == "los":
        result = score_los(fhir_base_url, patient_id)
        resource = build_los_risk_assessment(patient_id, result)
    elif model == "noshow":
        if not appointment_id:
            raise HTTPException(status_code=400, detail="noshow scoring requires an appointment_id query param")
        result = score_noshow(fhir_base_url, patient_id, appointment_id)
        resource = build_risk_assessment(patient_id, result, "appointment no-show")
    else:
        raise HTTPException(status_code=404, detail=f"Unknown model '{model}'. Must be one of: readmission, los, noshow.")

    write_risk_assessment(fhir_base_url, patient_id, resource)

    response = {
        "patient_id": patient_id,
        "model": model,
        "confidence": result["confidence"],
        "drivers": result["drivers"],
        "risk_assessment_id": resource["id"],
        "role": role,
    }
    if model == "los":
        response["point_days"] = result["point_days"]
        response["interval_80_low_days"] = result["interval_80_low_days"]
        response["interval_80_high_days"] = result["interval_80_high_days"]
    else:
        response["probability"] = result["probability"]
    return response
