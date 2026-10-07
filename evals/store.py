"""Persisted eval run history (SPEC section 11: "nightly live run; results
in ops.eval_runs and the Quality dashboard"). One row per eval-set run,
written by .github/workflows/nightly.yml and readable by the care-team
dashboard's Quality view (GET /v1/qa/overview's `recent_eval_runs`).

Lives in its own module rather than trustcore/db.py's schema SQL --
trustcore owns the audit hash chain specifically, not general operational
storage, the same reasoning qa/store.py and hie/db.py already follow for
their own schema pieces.
"""

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime

import psycopg

DEFAULT_DSN = "postgresql://careflow:careflow@localhost:5544/careflow"

_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.eval_runs (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL,
    eval_set TEXT NOT NULL,
    total INT NOT NULL,
    passed INT NOT NULL,
    pass_rate DOUBLE PRECISION NOT NULL,
    gate DOUBLE PRECISION,
    gate_met BOOLEAN,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
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


def record_run(
    eval_set: str,
    total: int,
    passed: int,
    gate: float | None = None,
    details: dict | None = None,
) -> None:
    pass_rate = passed / total if total else 0.0
    gate_met = (pass_rate >= gate) if gate is not None else None
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ops.eval_runs (ts, eval_set, total, passed, pass_rate, gate, gate_met, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    datetime.now(UTC),
                    eval_set,
                    total,
                    passed,
                    pass_rate,
                    gate,
                    gate_met,
                    json.dumps(details or {}),
                ),
            )
        conn.commit()
    finally:
        conn.close()


@dataclass(frozen=True)
class EvalRunRow:
    id: int
    ts: str
    eval_set: str
    total: int
    passed: int
    pass_rate: float
    gate: float | None
    gate_met: bool | None


def recent_runs(limit: int = 20) -> list[EvalRunRow]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, ts, eval_set, total, passed, pass_rate, gate, gate_met "
                "FROM ops.eval_runs ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        EvalRunRow(
            id=r[0], ts=r[1].isoformat(), eval_set=r[2], total=r[3], passed=r[4], pass_rate=r[5], gate=r[6], gate_met=r[7]
        )
        for r in rows
    ]
