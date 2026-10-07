"""Walk the audit chain and confirm no record has been altered.

Recomputes each record's hash from its own stored columns (via the same
canonical_payload() used when writing) rather than trusting any stored copy
of the payload -- so tampering with any single column is detectable, not
just tampering with prev_hash/hash themselves.
"""

import hashlib
from dataclasses import dataclass

import psycopg

from trustcore import db
from trustcore.audit import canonical_payload

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    checked: int
    first_bad_id: int | None
    reason: str | None


def verify_chain(conn: psycopg.Connection | None = None) -> VerifyResult:
    owns_conn = conn is None
    conn = conn or db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ts, actor, actor_role, action, resource_type, resource_id,
                       result, reason, prev_hash, hash
                FROM ops.audit_log ORDER BY id ASC
                """
            )
            rows = cur.fetchall()

        expected_prev = GENESIS_HASH
        for row in rows:
            (
                row_id,
                ts,
                actor,
                actor_role,
                action,
                resource_type,
                resource_id,
                result,
                reason,
                prev_hash,
                hash_,
            ) = row

            if prev_hash != expected_prev:
                return VerifyResult(
                    ok=False, checked=len(rows), first_bad_id=row_id, reason="broken chain link (prev_hash)"
                )

            payload = canonical_payload(
                ts, actor, actor_role, action, resource_type, resource_id, result, reason, prev_hash
            )
            recomputed = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if recomputed != hash_:
                return VerifyResult(
                    ok=False, checked=len(rows), first_bad_id=row_id, reason="hash does not match stored columns"
                )
            expected_prev = hash_

        return VerifyResult(ok=True, checked=len(rows), first_bad_id=None, reason=None)
    finally:
        if owns_conn:
            conn.close()
