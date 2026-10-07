"""Postgres connection + schema bootstrap for the trustcore audit chain."""

import os

import psycopg

DEFAULT_DSN = "postgresql://careflow:careflow@localhost:5544/careflow"

_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.audit_log (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL,
    actor TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    result TEXT NOT NULL CHECK (result IN ('allow', 'deny', 'error')),
    reason TEXT,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ops.audit_chain_head (
    id INT PRIMARY KEY DEFAULT 1,
    last_hash TEXT NOT NULL,
    CHECK (id = 1)
);

INSERT INTO ops.audit_chain_head (id, last_hash)
VALUES (1, repeat('0', 64))
ON CONFLICT (id) DO NOTHING;
"""


def dsn() -> str:
    return os.environ.get("CAREFLOW_DB_DSN", DEFAULT_DSN)


def connect() -> psycopg.Connection:
    return psycopg.connect(dsn())


def ensure_schema(conn: psycopg.Connection | None = None) -> None:
    owns_conn = conn is None
    conn = conn or connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()
