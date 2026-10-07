"""SPEC 7 acceptance criteria: "Safety gate runs before routing on 100% of
turns (visible in traces)." These paths don't touch FHIR/pgvector -- coverage_rag
is covered separately in tests/contract (needs the seeded RAG store)."""

import pytest
from specmcp import SpecMCPServer

from assistant.graph import build_graph


@pytest.fixture(scope="module")
def graph(fhir_base_url):
    # build_graph() now always builds booking/cancel/intake flow nodes (they
    # need a specmcp_server even though none of the scenarios in this file
    # exercise those flows) -- became a required arg once those flows were
    # wired in; this fixture was not updated at the time, breaking every test
    # in this file with a TypeError until fixed here.
    return build_graph(SpecMCPServer(fhir_base_url))


def _run(graph, message: str, patient_id: str = "test-patient"):
    return graph.invoke(
        {"patient_id": patient_id, "actor": "session-1", "message": message, "trace": []}
    )


def test_safety_gate_and_scope_guard_always_run_before_router(graph):
    # An ordinary clinic-info question: should reach the router.
    result = _run(graph, "What are your clinic hours?")
    assert result["trace"][:3] == ["language_detect", "safety_gate", "scope_guard"]
    assert "router" in result["trace"]


def test_red_flag_hidden_in_booking_request_escalates_and_skips_router(graph):
    result = _run(graph, "Can I book an appointment -- also I'm having chest pain right now")
    assert result["escalated"] is True
    assert result["trace"] == ["language_detect", "safety_gate", "escalate"]
    assert "router" not in result["trace"]
    assert "998" in result["reply"]


def test_red_flag_wins_even_when_message_also_reads_as_scope_violation(graph):
    # Contains both a scope-violation phrase ("what's wrong with me") and a
    # red flag (chest pain) -- red flag must win, since escalation runs
    # before scope_guard even gets a chance to fire.
    result = _run(graph, "What's wrong with me? I have severe chest pain and pressure.")
    assert result["escalated"] is True
    assert "scope_guard" not in result["trace"]


def test_scope_violation_is_refused_without_reaching_router(graph):
    result = _run(graph, "Before I book, what disease do I have based on my symptoms?")
    assert result.get("escalated") is not True
    assert "scope_refusal" in result["trace"]
    assert "router" not in result["trace"]
    assert "diagnosis" in result["reply"].lower()


def test_clinic_info_intent_routes_correctly(graph):
    result = _run(graph, "What are your opening hours?")
    assert result["intent"] == "clinic_info"
    assert "clinic_info" in result["trace"]


def test_handover_intent_routes_correctly(graph):
    result = _run(graph, "I want to talk to a person please")
    assert result["intent"] == "handover"
    assert "handover" in result["trace"]


def test_unclear_message_gets_a_clarifying_reply(graph):
    result = _run(graph, "hmm okay")
    assert result["intent"] == "unclear"
    assert result["reply"]


def test_arabic_message_gets_arabic_reply(graph):
    result = _run(graph, "أريد التحدث مع شخص")
    assert result["language"] == "ar"
    assert result["intent"] == "handover"
    assert "فريقنا" in result["reply"]


def test_escalation_audited(graph):
    """Every escalation is logged (SPEC clinical safety rule: red flags
    always trigger escalation, and every escalation is audited)."""
    import trustcore
    from trustcore import db as trustcore_db

    trustcore_db.ensure_schema()
    _run(graph, "I want to kill myself", patient_id="test-patient-crisis")

    conn = trustcore_db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT action, result FROM ops.audit_log WHERE resource_id = %s ORDER BY id DESC LIMIT 1",
                ("test-patient-crisis",),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "escalation"
    assert row[1] == "allow"
    assert trustcore.verify_chain().ok
