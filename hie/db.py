"""Storage for the HIE mock's shared-document record. Reuses trustcore's
Postgres connection helper (same `careflow` database, its own table) rather
than duplicating connection/DSN handling."""

import psycopg
from trustcore import db

_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.hie_documents (
    id BIGSERIAL PRIMARY KEY,
    patient_id TEXT NOT NULL,
    from_org TEXT NOT NULL,
    to_org TEXT NOT NULL,
    document_type TEXT NOT NULL,
    shared_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def ensure_schema(conn: psycopg.Connection | None = None) -> None:
    owns_conn = conn is None
    conn = conn or db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def insert_document(
    patient_id: str, from_org: str, to_org: str, document_type: str, conn: psycopg.Connection | None = None
) -> dict:
    owns_conn = conn is None
    conn = conn or db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ops.hie_documents (patient_id, from_org, to_org, document_type)
                VALUES (%s, %s, %s, %s)
                RETURNING id, shared_at
                """,
                (patient_id, from_org, to_org, document_type),
            )
            row_id, shared_at = cur.fetchone()
        if owns_conn:
            conn.commit()
        return {"id": row_id, "shared_at": shared_at.isoformat()}
    finally:
        if owns_conn:
            conn.close()


def list_documents(patient_id: str, conn: psycopg.Connection | None = None) -> list[dict]:
    owns_conn = conn is None
    conn = conn or db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, patient_id, from_org, to_org, document_type, shared_at
                FROM ops.hie_documents
                WHERE patient_id = %s
                ORDER BY shared_at DESC
                """,
                (patient_id,),
            )
            rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "patient_id": r[1],
                "from_org": r[2],
                "to_org": r[3],
                "document_type": r[4],
                "shared_at": r[5].isoformat(),
            }
            for r in rows
        ]
    finally:
        if owns_conn:
            conn.close()
