"""SPEC section 10 stretch module: claims pre-check agent, exposed over the
same role-gated API pattern as every other layer. Gated to "admin" -- this
portfolio project has no dedicated billing/coder role, and admin is already
the stand-in used elsewhere (e.g. apps/api/routers/qa.py) for back-office
access without a real login system.

POST /v1/claims/precheck never changes anything -- it only returns flags
(SPEC acceptance criterion: "No automatic changes to claims"). A coder's
decision on a flag is a separate, explicit, audited action
(POST /v1/claims/decisions -> claims/store.py's record_decision(), which
also writes a trustcore audit record).
"""

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.dependencies import require_role
from claims.agent import precheck_claim
from claims.schema import ClaimLine, DraftClaim
from claims.store import DECISIONS, recent_decisions, record_decision, record_precheck_run

router = APIRouter()


class ClaimLineRequest(BaseModel):
    line_id: str
    service_type: str
    diagnosis_code: str
    procedure_code: str
    amount_aed: float
    encounter_documentation: str
    session_number: int | None = None


class DraftClaimRequest(BaseModel):
    claim_id: str
    patient_id: str
    practitioner_id: str
    plan_name: str
    policy_start_date: date
    service_date: date
    pre_authorization_obtained: bool
    lines: list[ClaimLineRequest]


class DecisionRequest(BaseModel):
    claim_id: str
    flag_type: str
    decision: str  # "accept" | "override" | "dismiss"
    coder_id: str
    line_id: str | None = None
    note: str | None = None


def _to_draft_claim(body: DraftClaimRequest) -> DraftClaim:
    return DraftClaim(
        claim_id=body.claim_id,
        patient_id=body.patient_id,
        practitioner_id=body.practitioner_id,
        plan_name=body.plan_name,
        policy_start_date=body.policy_start_date,
        service_date=body.service_date,
        pre_authorization_obtained=body.pre_authorization_obtained,
        lines=[ClaimLine(**line.model_dump()) for line in body.lines],
    )


@router.post("/v1/claims/precheck")
def precheck(body: DraftClaimRequest, role: str = Depends(require_role("admin"))):
    result = precheck_claim(_to_draft_claim(body))
    record_precheck_run(result)
    return {
        "claim_id": result.claim_id,
        "clean": result.clean,
        "flags": [asdict(f) for f in result.flags],
    }


@router.post("/v1/claims/decisions")
def post_decision(body: DecisionRequest, role: str = Depends(require_role("admin"))):
    record_decision(
        claim_id=body.claim_id,
        flag_type=body.flag_type,
        decision=body.decision,
        coder_id=body.coder_id,
        line_id=body.line_id,
        note=body.note,
    )
    return {"recorded": True}


@router.get("/v1/claims/decisions")
def get_decisions(role: str = Depends(require_role("admin"))):
    return {"decisions": [asdict(d) for d in recent_decisions()]}


__all__ = ["DECISIONS", "router"]
