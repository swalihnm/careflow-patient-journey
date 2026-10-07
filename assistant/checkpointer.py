"""Postgres-backed LangGraph checkpointer: multi-turn conversation state
(booking/cancel/intake progress) persists across API server restarts,
sharing the same Postgres instance as everything else in this repo rather
than needing a separate store.
"""

from langgraph.checkpoint.postgres import PostgresSaver
from trustcore.db import connect


def build_checkpointer() -> PostgresSaver:
    conn = connect()
    conn.autocommit = True  # required by PostgresSaver's internal transaction handling
    saver = PostgresSaver(conn)
    saver.setup()  # idempotent; creates the checkpoint tables on first run
    return saver
