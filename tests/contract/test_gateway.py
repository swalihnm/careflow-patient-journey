"""trustcore.gateway: the pluggable LLM entry point (CLAUDE.md: "all LLM
calls through trustcore.gateway"). Tests the not-configured path by clearing
every provider key gateway.py checks (including OLLAMA_API_KEY, which IS set
in this repo's .env as of the Ollama Cloud integration -- see PROGRESS.md) --
these tests assert the behaviour when none of them are present, regardless of
what's actually configured in this environment."""

import pytest
from trustcore.gateway import LLMNotConfigured, is_configured


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch):
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OLLAMA_API_KEY", "LITELLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_is_configured_false_without_any_key():
    assert is_configured() is False


def test_is_configured_true_with_anthropic_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    assert is_configured() is True


def test_complete_raises_not_configured_without_a_key():
    from trustcore.gateway import complete

    with pytest.raises(LLMNotConfigured):
        complete(messages=[{"role": "user", "content": "hello"}])


def test_complete_denial_is_audited(monkeypatch):
    from trustcore import db as trustcore_db
    from trustcore.gateway import complete

    trustcore_db.ensure_schema()
    with pytest.raises(LLMNotConfigured):
        complete(messages=[{"role": "user", "content": "hello"}], actor="test-gateway-audit")

    conn = trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT action, result, reason FROM ops.audit_log WHERE actor = %s ORDER BY id DESC LIMIT 1",
                ("test-gateway-audit",),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "llm_call"
    assert row[1] == "deny"
    assert "no llm api key configured" in row[2].lower()
