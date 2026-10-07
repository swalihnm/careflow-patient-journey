"""GET /v1/escalations (SPEC 9): open escalations with reason and transcript
excerpt, for the nurse view. Reads trustcore's audit chain directly --
every escalation is already an audited event (assistant/escalate.py), so
there's a single source of truth to query, not a parallel "escalations"
table that could drift from what was actually logged.
"""

from fastapi import APIRouter, Depends
from trustcore import db as trustcore_db

from apps.api.dependencies import require_role
from assistant.transcript import get_transcript

router = APIRouter()


@router.get("/v1/escalations")
def list_escalations(limit: int = 50, role: str = Depends(require_role("nurse", "clinician", "admin"))):
    conn = trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ts, actor, resource_id, reason
                FROM ops.audit_log
                WHERE action = 'escalation'
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    escalations = []
    for row_id, ts, thread_id, patient_id, reason in rows:
        transcript = get_transcript(thread_id)
        excerpt = transcript[-4:] if transcript else []
        escalations.append(
            {
                "audit_id": row_id,
                "timestamp": ts.isoformat(),
                "thread_id": thread_id,
                "patient_id": patient_id,
                "reason": reason,
                "transcript_excerpt": excerpt,
            }
        )

    return {"escalations": escalations, "role": role}
