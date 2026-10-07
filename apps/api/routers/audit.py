"""GET /v1/audit (SPEC 9): filterable audit log + chain verification.

Auditor role sees masked actor/resource_id per SPEC section 5's field-masking
table ("Auditor: aggregates only" for risk scores, masked identifiers
elsewhere) -- reuses specmcp.mask.apply_mask so the masking behaviour is the
same primitive used everywhere else in the repo, not a second implementation.
"""

from fastapi import APIRouter, Depends
from specmcp.mask import apply_mask
from trustcore import db as trustcore_db
from trustcore import verify_chain

from apps.api.dependencies import require_role

router = APIRouter()


@router.get("/v1/audit")
def audit_log(
    action: str | None = None,
    limit: int = 100,
    role: str = Depends(require_role("auditor", "admin")),
):
    conn = trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            if action:
                cur.execute(
                    "SELECT id, ts, actor, actor_role, action, resource_type, resource_id, result, reason "
                    "FROM ops.audit_log WHERE action = %s ORDER BY id DESC LIMIT %s",
                    (action, limit),
                )
            else:
                cur.execute(
                    "SELECT id, ts, actor, actor_role, action, resource_type, resource_id, result, reason "
                    "FROM ops.audit_log ORDER BY id DESC LIMIT %s",
                    (limit,),
                )
            rows = cur.fetchall()
    finally:
        conn.close()

    events = []
    for row_id, ts, actor, actor_role, action_name, resource_type, resource_id, result, reason in rows:
        event = {
            "id": row_id,
            "timestamp": ts.isoformat(),
            "actor": actor,
            "actor_role": actor_role,
            "action": action_name,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "result": result,
            "reason": reason,
        }
        if role == "auditor":
            event = apply_mask(event, ["actor", "resource_id"])
        events.append(event)

    chain = verify_chain()
    return {
        "events": events,
        "chain_status": {"ok": chain.ok, "checked": chain.checked, "first_bad_id": chain.first_bad_id},
        "role": role,
    }
