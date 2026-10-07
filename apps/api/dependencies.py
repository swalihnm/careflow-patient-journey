"""Shared FastAPI dependencies: role-based access (SPEC section 5's masking
table + section 9's per-endpoint role column) and the app-lifetime singletons
(specmcp server, compiled graph) built once in main.py's lifespan and stored
on `app.state`.

Role enforcement here is a header (`X-Role`), not real authentication --
there's no login system in this portfolio project. What IS real is the
access-control *logic* driven by that role: SPEC's explicit acceptance
criterion "Patients never see risk scores (API role tests)" is enforced
server-side below, tested the same way any other role check would be.
"""

import os
from typing import Literal

from fastapi import Header, HTTPException, Request

Role = Literal["patient", "clinician", "nurse", "auditor", "admin", "system"]
ALL_ROLES: tuple[Role, ...] = ("patient", "clinician", "nurse", "auditor", "admin", "system")


def get_role(x_role: str = Header(default="patient")) -> Role:
    if x_role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role '{x_role}'. Must be one of {ALL_ROLES}.")
    return x_role  # type: ignore[return-value]


def require_role(*allowed: Role):
    # `role` is typed `str`, not `Role`, deliberately: a `Literal` annotation
    # here would make FastAPI/Pydantic validate it *before* this function
    # body runs, rejecting an unknown role with a generic 422 instead of the
    # clearer 400 + message below (verified: that's exactly what happened
    # with the Literal annotation -- the "unknown role" branch was dead code).
    def _dependency(role: str = Header(default="patient", alias="X-Role")) -> Role:
        if role not in ALL_ROLES:
            raise HTTPException(status_code=400, detail=f"Unknown role '{role}'. Must be one of {ALL_ROLES}.")
        if role not in allowed:
            raise HTTPException(status_code=403, detail=f"Role '{role}' cannot access this endpoint.")
        return role  # type: ignore[return-value]

    return _dependency


def get_fhir_base_url() -> str:
    return os.environ.get("CAREFLOW_FHIR_BASE_URL", "http://localhost:8210/fhir")


def get_specmcp_server(request: Request):
    return request.app.state.specmcp_server


def get_graph(request: Request):
    return request.app.state.graph
