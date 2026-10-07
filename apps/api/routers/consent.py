"""POST /v1/consent (SPEC 9, F15): record or withdraw consent as a FHIR
Consent resource. Two categories, matching SPEC section 4's patient journey:
"ai-intake" (AI-assisted intake/booking) and "hie-share" (cross-clinic
record sharing -- hie/consent.py's HIE_SHARE_CATEGORY, reused here so the
HIE mock's own consent check (SPEC 5) reads exactly what this endpoint writes).
"""

from typing import Literal

import httpx
import trustcore
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apps.api.dependencies import get_fhir_base_url
from hie.consent import CONSENT_CATEGORY_SYSTEM, HIE_SHARE_CATEGORY

router = APIRouter()

AI_INTAKE_CATEGORY = "ai-intake"
ConsentCategory = Literal["ai-intake", "hie-share"]


class ConsentRequest(BaseModel):
    patient_id: str
    category: ConsentCategory
    active: bool  # True = grant, False = withdraw


def _build_consent_resource(patient_id: str, category: str, active: bool) -> dict:
    return {
        "resourceType": "Consent",
        "id": f"consent-{patient_id}-{category}",
        "status": "active" if active else "inactive",
        "scope": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/consentscope", "code": "patient-privacy"}]
        },
        "category": [{"coding": [{"system": CONSENT_CATEGORY_SYSTEM, "code": category}]}],
        "patient": {"reference": f"Patient/{patient_id}"},
    }


@router.post("/v1/consent")
def set_consent(body: ConsentRequest, fhir_base_url: str = Depends(get_fhir_base_url)):
    resource = _build_consent_resource(body.patient_id, body.category, body.active)

    with httpx.Client(timeout=10.0) as client:
        resp = client.put(f"{fhir_base_url}/Consent/{resource['id']}", json=resource)
        if resp.status_code == 400:
            # HAPI enforces referential integrity: a Consent can't reference
            # a Patient it doesn't have on file ("HAPI-1094: Resource ...
            # not found"). A clear 404 here beats letting an unhandled
            # httpx.HTTPStatusError reach the top as a generic 500 -- found
            # via a real bug where that 500 then showed up in the browser as
            # a misleading CORS error, since Starlette's CORS middleware
            # doesn't attach its headers to a response an unhandled
            # exception produced.
            raise HTTPException(
                status_code=404,
                detail=f"Patient '{body.patient_id}' not found -- consent requires an existing FHIR Patient.",
            )
        resp.raise_for_status()

    trustcore.record(
        actor=body.patient_id,
        actor_role="patient",
        action="consent_change",
        resource_type="Consent",
        resource_id=resource["id"],
        result="allow",
        reason=f"category={body.category} active={body.active}",
    )

    return {"id": resource["id"], "status": resource["status"], "category": body.category}


__all__ = ["AI_INTAKE_CATEGORY", "HIE_SHARE_CATEGORY", "router"]
