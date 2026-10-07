"""Persisted claim pre-check runs + human coder decisions on flags (SPEC 10
acceptance criterion: "No automatic changes to claims; all suggestions
require human action (audited)"). Own schema module (`claims`), not bolted
onto trustcore/db.py, same reasoning qa/store.py and evals/store.py already
follow for their own schema pieces -- trustcore owns the audit hash chain
specifically. Every decision additionally writes a trustcore.audit record, so
"audited" means the same tamper-evident chain the rest of the repo relies on,
not a second, weaker audit mechanism.
"""

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime

import psycopg
from trustcore import audit as trustcore_audit

from claims.schema import ClaimPrecheckResult

DEFAULT_DSN = "postgresql://careflow:careflow@localhost:5544/careflow"

_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS claims;

CREATE TABLE IF NOT EXISTS claims.precheck_runs (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL,
    claim_id TEXT NOT NULL,
    flag_count INT NOT NULL,
    flags JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS claims.flag_decisions (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL,
    claim_id TEXT NOT NULL,
    flag_type TEXT NOT NULL,
    line_id TEXT,
    decision TEXT NOT NULL,
    coder_id TEXT NOT NULL,
    note TEXT
);
"""


def _dsn() -> str:
    return os.environ.get("CAREFLOW_DB_DSN", DEFAULT_DSN)


def _connect() -> psycopg.Connection:
    return psycopg.connect(_dsn())


def ensure_schema(conn: psycopg.Connection | None = None) -> None:
    owns_conn = conn is None
    conn = conn or _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def record_precheck_run(result: ClaimPrecheckResult) -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO claims.precheck_runs (ts, claim_id, flag_count, flags) VALUES (%s, %s, %s, %s)",
                (
                    datetime.now(UTC),
                    result.claim_id,
                    len(result.flags),
                    json.dumps([vars(f) for f in result.flags]),
                ),
            )
        conn.commit()
    finally:
        conn.close()


DECISIONS = ("accept", "override", "dismiss")


def record_decision(
    claim_id: str,
    flag_type: str,
    decision: str,
    coder_id: str,
    line_id: str | None = None,
    note: str | None = None,
) -> None:
    """Records a human coder's decision on one flag and writes a matching
    audit record -- this is the "human action (audited)" SPEC's acceptance
    criterion asks for; precheck_claim() itself never changes anything."""
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}, got {decision!r}")

    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO claims.flag_decisions (ts, claim_id, flag_type, line_id, decision, coder_id, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (datetime.now(UTC), claim_id, flag_type, line_id, decision, coder_id, note),
            )
        conn.commit()
        trustcore_audit.record(
            actor=coder_id,
            actor_role="admin",
            action=f"claims.flag_decision.{decision}",
            resource_type="Claim",
            resource_id=claim_id,
            result="allow",
            reason=f"flag_type={flag_type} line_id={line_id} note={note}",
            conn=conn,
        )
    finally:
        conn.close()


@dataclass(frozen=True)
class FlagDecisionRow:
    id: int
    ts: str
    claim_id: str
    flag_type: str
    line_id: str | None
    decision: str
    coder_id: str
    note: str | None


def recent_decisions(limit: int = 50) -> list[FlagDecisionRow]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, ts, claim_id, flag_type, line_id, decision, coder_id, note "
                "FROM claims.flag_decisions ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        FlagDecisionRow(
            id=r[0], ts=r[1].isoformat(), claim_id=r[2], flag_type=r[3], line_id=r[4], decision=r[5], coder_id=r[6], note=r[7]
        )
        for r in rows
    ]
