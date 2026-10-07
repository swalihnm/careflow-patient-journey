"""Append-only, tamper-evident audit log.

Every record hashes (prev_hash, ts, actor, action, resource, result) so the chain
is tamper-evident: altering any past record's columns breaks that record's hash
against the recomputed canonical payload, and every hash after it, and
trustcore.verify.verify_chain() (which recomputes hashes from the stored columns,
not from a separately-stored copy) will detect exactly where the chain broke.

False alarms in the rest of the system are acceptable; a silently-lost or
silently-altered audit record is not, so writes happen inside a single DB
transaction that serializes on the chain head (SELECT ... FOR UPDATE) to avoid
concurrent writers racing on prev_hash.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

import psycopg

from trustcore import db

Result = str  # "allow" | "deny" | "error"


@dataclass(frozen=True)
class AuditRecord:
    id: int
    ts: datetime
    actor: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: str | None
    result: Result
    reason: str | None
    prev_hash: str
    hash: str


def canonical_payload(
    ts: datetime,
    actor: str,
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: str | None,
    result: str,
    reason: str | None,
    prev_hash: str,
) -> str:
    """The exact string that gets hashed. verify.py rebuilds this from the
    stored columns (not from a redundant stored copy) so that tampering with
    any single column -- not just prev_hash/hash -- is detectable."""
    payload = {
        "ts": ts.astimezone(UTC).isoformat(),
        "actor": actor,
        "actor_role": actor_role,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "result": result,
        "reason": reason,
        "prev_hash": prev_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def record(
    actor: str,
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    result: Result = "allow",
    reason: str | None = None,
    conn: psycopg.Connection | None = None,
) -> AuditRecord:
    """Append one tamper-evident audit record and return it.

    Safe to call with an externally-managed `conn` (e.g. to fold the audit
    write into the same transaction as the action it describes); otherwise
    opens and closes its own connection.
    """
    owns_conn = conn is None
    conn = conn or db.connect()
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT last_hash FROM ops.audit_chain_head WHERE id = 1 FOR UPDATE")
            row = cur.fetchone()
            prev_hash = row[0]

            ts = datetime.now(UTC)
            payload = canonical_payload(
                ts, actor, actor_role, action, resource_type, resource_id, result, reason, prev_hash
            )
            new_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

            cur.execute(
                """
                    INSERT INTO ops.audit_log
                        (ts, actor, actor_role, action, resource_type, resource_id,
                         result, reason, prev_hash, hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                (
                    ts,
                    actor,
                    actor_role,
                    action,
                    resource_type,
                    resource_id,
                    result,
                    reason,
                    prev_hash,
                    new_hash,
                ),
            )
            row_id = cur.fetchone()[0]

            cur.execute("UPDATE ops.audit_chain_head SET last_hash = %s WHERE id = 1", (new_hash,))
        return AuditRecord(
            id=row_id,
            ts=ts,
            actor=actor,
            actor_role=actor_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            reason=reason,
            prev_hash=prev_hash,
            hash=new_hash,
        )
    finally:
        if owns_conn:
            conn.close()
