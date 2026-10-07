"""CareFlow API (SPEC 9): one FastAPI backend, role-gated, backed by the
same FHIR server, trustcore audit chain, and LangGraph assistant used
throughout this repo -- nothing here is a separate mock of those.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from specmcp import SpecMCPServer
from trustcore import db as trustcore_db

from apps.api.dependencies import get_fhir_base_url
from apps.api.routers import (
    audit,
    chat,
    claims,
    consent,
    escalations,
    experiments,
    patients,
    qa,
    risk,
)
from assistant.checkpointer import build_checkpointer
from assistant.graph import build_graph
from assistant.transcript import ensure_schema as ensure_transcript_schema
from claims.store import ensure_schema as ensure_claims_schema
from evals.store import ensure_schema as ensure_eval_runs_schema
from hie.db import ensure_schema as ensure_hie_schema
from qa.store import ensure_schema as ensure_qa_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    trustcore_db.ensure_schema()
    ensure_hie_schema()
    ensure_transcript_schema()
    ensure_qa_schema()
    ensure_eval_runs_schema()
    ensure_claims_schema()

    fhir_base_url = get_fhir_base_url()
    specmcp_server = SpecMCPServer(fhir_base_url)
    checkpointer = build_checkpointer()

    app.state.specmcp_server = specmcp_server
    app.state.graph = build_graph(specmcp_server, checkpointer=checkpointer)

    yield


app = FastAPI(title="CareFlow API", version="0.1.0", lifespan=lifespan)

# Local dev only: the two Next.js apps (apps/care-web, apps/patient-web) run
# on their own dev-server ports and call this API cross-origin. There's no
# real deployment target for this portfolio project, so this is deliberately
# permissive rather than configured per-environment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3010", "http://localhost:3011"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(consent.router)
app.include_router(patients.router)
app.include_router(risk.router)
app.include_router(escalations.router)
app.include_router(experiments.router)
app.include_router(qa.router)
app.include_router(audit.router)
app.include_router(claims.router)


@app.get("/health")
def health():
    return {"status": "ok"}
