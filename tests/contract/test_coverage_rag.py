"""Coverage RAG (SPEC 7 node 6 + acceptance criteria: "Coverage answers cite
the plan section; low-confidence answers hand over"). Needs the seeded
pgvector store: `uv run python -m rag.store` first."""

from specmcp import SpecMCPServer

from assistant.coverage import answer_coverage_question
from assistant.graph import build_graph


def test_coverage_question_is_grounded_with_citation():
    answer = answer_coverage_question("Does my plan cover physiotherapy?", language="en")
    assert answer.grounded
    assert answer.citation is not None
    assert "Source" in answer.text


def test_coverage_question_answered_in_arabic_for_arabic_query():
    answer = answer_coverage_question("هل يغطي تأميني العلاج الطبيعي؟", language="ar")
    assert answer.grounded
    assert answer.chunk.language == "ar"
    assert "المصدر" in answer.text


def test_unrelated_question_hands_over_instead_of_hallucinating():
    answer = answer_coverage_question("What's the capital of France?", language="en")
    assert not answer.grounded
    assert "connect you" in answer.text.lower()


def test_graph_coverage_question_end_to_end(fhir_base_url):
    # build_graph() now always builds booking/cancel/intake flow nodes, which
    # need a specmcp_server -- became a required arg once those flows were
    # wired in; this test wasn't updated at the time, breaking it with a
    # TypeError.
    graph = build_graph(SpecMCPServer(fhir_base_url))
    result = graph.invoke(
        {
            "patient_id": "test-patient",
            "actor": "session-1",
            "message": "Does my insurance cover physiotherapy sessions?",
            "trace": [],
        }
    )
    assert result["intent"] == "coverage_question"
    assert "coverage_rag" in result["trace"]
    assert "Source" in result["reply"] or "المصدر" in result["reply"]
