"""Storage for QA judge scores (SPEC 3's `qa` schema)."""

import json

import psycopg
from trustcore import db as trustcore_db

from qa.judge import JudgeScore

_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS qa;

CREATE TABLE IF NOT EXISTS qa.judge_scores (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    rubric_version TEXT NOT NULL,
    safety TEXT NOT NULL CHECK (safety IN ('pass', 'fail')),
    safety_justification TEXT NOT NULL,
    accuracy INT NOT NULL,
    accuracy_justification TEXT NOT NULL,
    grounding INT NOT NULL,
    grounding_justification TEXT NOT NULL,
    privacy TEXT NOT NULL CHECK (privacy IN ('pass', 'fail')),
    privacy_justification TEXT NOT NULL,
    tone_and_empathy INT NOT NULL,
    tone_and_empathy_justification TEXT NOT NULL,
    language_quality INT NOT NULL,
    language_quality_justification TEXT NOT NULL,
    failure_tags JSONB NOT NULL,
    raw_model TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS qa.human_labels (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    human_value TEXT NOT NULL,
    labeller TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (thread_id, dimension, labeller)
);
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


def save_score(thread_id: str, score: JudgeScore, conn: psycopg.Connection | None = None) -> int:
    owns_conn = conn is None
    conn = conn or trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO qa.judge_scores
                    (thread_id, rubric_version, safety, safety_justification, accuracy, accuracy_justification,
                     grounding, grounding_justification, privacy, privacy_justification,
                     tone_and_empathy, tone_and_empathy_justification, language_quality,
                     language_quality_justification, failure_tags, raw_model)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    thread_id,
                    score.rubric_version,
                    score.safety,
                    score.safety_justification,
                    score.accuracy,
                    score.accuracy_justification,
                    score.grounding,
                    score.grounding_justification,
                    score.privacy,
                    score.privacy_justification,
                    score.tone_and_empathy,
                    score.tone_and_empathy_justification,
                    score.language_quality,
                    score.language_quality_justification,
                    json.dumps(score.failure_tags),
                    score.raw_model,
                ),
            )
            row_id = cur.fetchone()[0]
        if owns_conn:
            conn.commit()
        return row_id
    finally:
        if owns_conn:
            conn.close()


def save_human_label(
    thread_id: str, dimension: str, value: str, labeller: str, conn: psycopg.Connection | None = None
) -> None:
    owns_conn = conn is None
    conn = conn or trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO qa.human_labels (thread_id, dimension, human_value, labeller)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (thread_id, dimension, labeller) DO UPDATE SET human_value = EXCLUDED.human_value
                """,
                (thread_id, dimension, value, labeller),
            )
        if owns_conn:
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


def overview(conn: psycopg.Connection | None = None) -> dict:
    """Aggregate scores for the /v1/qa/overview dashboard endpoint."""
    owns_conn = conn is None
    conn = conn or trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM qa.judge_scores")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM qa.judge_scores WHERE safety = 'fail'")
            safety_fails = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM qa.judge_scores WHERE privacy = 'fail'")
            privacy_fails = cur.fetchone()[0]
            cur.execute(
                "SELECT AVG(accuracy), AVG(grounding), AVG(tone_and_empathy), AVG(language_quality) "
                "FROM qa.judge_scores"
            )
            avgs = cur.fetchone()
            cur.execute(
                "SELECT failure_tags FROM qa.judge_scores WHERE failure_tags != '[]'::jsonb"
            )
            tag_rows = cur.fetchall()
        tag_counts: dict[str, int] = {}
        for (tags,) in tag_rows:
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return {
            "total_scored": total,
            "safety_fail_count": safety_fails,
            "privacy_fail_count": privacy_fails,
            "avg_accuracy": float(avgs[0]) if avgs[0] is not None else None,
            "avg_grounding": float(avgs[1]) if avgs[1] is not None else None,
            "avg_tone_and_empathy": float(avgs[2]) if avgs[2] is not None else None,
            "avg_language_quality": float(avgs[3]) if avgs[3] is not None else None,
            "failure_tag_counts": tag_counts,
        }
    finally:
        if owns_conn:
            conn.close()
