"""HIE mock service: simulates consent-gated record sharing between two clinics.

Every share attempt — allowed or denied — is an audit event (SPEC section 5
acceptance criteria: "HIE sharing fails without a valid Consent (tested)").
"""

import os
from contextlib import asynccontextmanager

import trustcore
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from trustcore import db as trustcore_db

from hie import consent
from hie import db as hie_db

FHIR_BASE_URL = os.environ.get("CAREFLOW_FHIR_BASE_URL", "http://localhost:8210/fhir")


@asynccontextmanager
async def lifespan(app: FastAPI):
    trustcore_db.ensure_schema()
    hie_db.ensure_schema()
    yield


app = FastAPI(title="CareFlow HIE mock", version="0.1.0", lifespan=lifespan)


class ShareRequest(BaseModel):
    patient_id: str
    from_org: str
    to_org: str
    document_type: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/share")
def share(req: ShareRequest):
    if not consent.has_active_consent(FHIR_BASE_URL, req.patient_id):
        trustcore.record(
            actor="hie-service",
            actor_role="system",
            action="hie_share",
            resource_type=req.document_type,
            resource_id=req.patient_id,
            result="deny",
            reason="no active hie-share Consent for this patient",
        )
        raise HTTPException(status_code=403, detail="no active consent to share records for this patient")

    doc = hie_db.insert_document(req.patient_id, req.from_org, req.to_org, req.document_type)
    trustcore.record(
        actor="hie-service",
        actor_role="system",
        action="hie_share",
        resource_type=req.document_type,
        resource_id=req.patient_id,
        result="allow",
        reason=None,
    )
    return {"shared": True, **doc}


@app.get("/documents")
def documents(patient_id: str):
    return hie_db.list_documents(patient_id)
