"""pgvector-backed storage for the policy RAG corpus (SPEC 3's `rag` store)."""

from dataclasses import dataclass
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from trustcore import db as trustcore_db

from rag.chunking import load_corpus
from rag.embeddings import EMBEDDING_DIM, embed, embed_one

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"

_SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS rag;

CREATE TABLE IF NOT EXISTS rag.policy_chunks (
    id BIGSERIAL PRIMARY KEY,
    document TEXT NOT NULL,
    section TEXT NOT NULL,
    language TEXT NOT NULL,
    version_date DATE NOT NULL,
    content TEXT NOT NULL,
    source_path TEXT NOT NULL,
    embedding vector({EMBEDDING_DIM}) NOT NULL,
    UNIQUE (document, section, language)
);
"""


def connect() -> psycopg.Connection:
    conn = trustcore_db.connect()
    register_vector(conn)
    return conn


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


def ingest_corpus(corpus_dir: Path = CORPUS_DIR, conn: psycopg.Connection | None = None) -> int:
    chunks = load_corpus(corpus_dir)
    if not chunks:
        return 0

    vectors = embed([c.content for c in chunks])

    owns_conn = conn is None
    conn = conn or connect()
    try:
        ensure_schema(conn)
        with conn.cursor() as cur:
            for chunk, vector in zip(chunks, vectors, strict=True):
                cur.execute(
                    """
                    INSERT INTO rag.policy_chunks
                        (document, section, language, version_date, content, source_path, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (document, section, language)
                    DO UPDATE SET
                        version_date = EXCLUDED.version_date,
                        content = EXCLUDED.content,
                        source_path = EXCLUDED.source_path,
                        embedding = EXCLUDED.embedding
                    """,
                    (
                        chunk.document,
                        chunk.section,
                        chunk.language,
                        chunk.version_date,
                        chunk.content,
                        chunk.source_path,
                        vector,
                    ),
                )
        if owns_conn:
            conn.commit()
        return len(chunks)
    finally:
        if owns_conn:
            conn.close()


@dataclass(frozen=True)
class RetrievedChunk:
    document: str
    section: str
    language: str
    version_date: str
    content: str
    distance: float


def query(
    text: str, k: int = 3, language: str | None = None, conn: psycopg.Connection | None = None
) -> list[RetrievedChunk]:
    """Similarity search. The embeddings are cross-lingual by design (SPEC 7:
    "retrieval searches both [languages]"), so an Arabic question can in
    principle match an English-only chunk more closely than any Arabic one --
    correct for *finding* the right content, wrong for *answering in the
    patient's language*. Pass `language` to restrict candidates to that
    language; the caller (assistant/coverage.py) always does this first and
    only drops the filter if nothing matches, so the answer is never
    returned in the wrong language purely because retrieval scored higher
    for the other one.
    """
    vector = embed_one(text)

    owns_conn = conn is None
    conn = conn or connect()
    try:
        with conn.cursor() as cur:
            if language:
                cur.execute(
                    """
                    SELECT document, section, language, version_date, content, embedding <=> %s::vector AS distance
                    FROM rag.policy_chunks
                    WHERE language = %s
                    ORDER BY distance ASC
                    LIMIT %s
                    """,
                    (vector, language, k),
                )
            else:
                cur.execute(
                    """
                    SELECT document, section, language, version_date, content, embedding <=> %s::vector AS distance
                    FROM rag.policy_chunks
                    ORDER BY distance ASC
                    LIMIT %s
                    """,
                    (vector, k),
                )
            rows = cur.fetchall()
        return [
            RetrievedChunk(
                document=r[0], section=r[1], language=r[2], version_date=str(r[3]), content=r[4], distance=r[5]
            )
            for r in rows
        ]
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    n = ingest_corpus()
    print(f"Ingested {n} policy chunks into rag.policy_chunks.")
