"""Conversation transcript storage (SPEC 3's `assistant` schema: "Conversations,
turns (PII-masked)"). Every turn is masked before it touches the database --
this is what the QA judge (qa/judge.py) reads from to score a finished
conversation, and the same masking guarantee the rest of the repo relies on
for logs/traces applies here too.
"""

from datetime import datetime

import psycopg
from trustcore import db as trustcore_db

from safety.masking import mask_text

_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS assistant;

CREATE TABLE IF NOT EXISTS assistant.conversation_turns (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    turn_index INT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('patient', 'assistant')),
    text TEXT NOT NULL,
    language TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversation_turns_thread_idx ON assistant.conversation_turns (thread_id, turn_index);
"""


def ensure_schema(conn: psycopg.Connection | None = None) -> None:
    owns_conn = conn is None
    conn = conn or trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def log_turn(
    thread_id: str,
    patient_id: str,
    role: str,
    text: str,
    language: str | None = None,
    conn: psycopg.Connection | None = None,
) -> None:
    masked = mask_text(text).masked_text

    owns_conn = conn is None
    conn = conn or trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(turn_index), -1) + 1 FROM assistant.conversation_turns WHERE thread_id = %s",
                (thread_id,),
            )
            next_index = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO assistant.conversation_turns (thread_id, patient_id, turn_index, role, text, language)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (thread_id, patient_id, next_index, role, masked, language),
            )
        if owns_conn:
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


def get_transcript(thread_id: str, conn: psycopg.Connection | None = None) -> list[dict]:
    owns_conn = conn is None
    conn = conn or trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, text, language, created_at
                FROM assistant.conversation_turns
                WHERE thread_id = %s
                ORDER BY turn_index ASC
                """,
                (thread_id,),
            )
            rows = cur.fetchall()
        return [
            {"role": r[0], "text": r[1], "language": r[2], "created_at": _iso(r[3])}
            for r in rows
        ]
    finally:
        if owns_conn:
            conn.close()


def list_thread_ids(conn: psycopg.Connection | None = None) -> list[str]:
    owns_conn = conn is None
    conn = conn or trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT thread_id FROM assistant.conversation_turns ORDER BY thread_id")
            return [r[0] for r in cur.fetchall()]
    finally:
        if owns_conn:
            conn.close()


def _iso(dt: datetime) -> str:
    return dt.isoformat()
