import pytest
import trustcore
from specmcp import PolicyDenied, SpecMCPServer


@pytest.fixture(scope="module")
def server(fhir_base_url):
    return SpecMCPServer(fhir_base_url)


def test_assistant_can_book_and_read_allowed_resources(server, test_patient_id):
    patient = server.call(
        "read_patient_demographics", {"id": test_patient_id}, actor="session-1", role="assistant"
    )
    assert patient["resourceType"] == "Patient"
    # masked per policy: assistant role hides identifier
    assert patient["identifier"] == "***MASKED***"

    coverage = server.call(
        "read_coverage", {"beneficiary": f"Patient/{test_patient_id}"}, actor="session-1", role="assistant"
    )
    assert coverage["resourceType"] == "Bundle"


def test_assistant_cannot_read_condition_and_it_is_audited(server, test_patient_id, latest_audit_row):
    """SPEC 5 acceptance criteria: reading a Condition through the assistant's
    tools returns a policy denial, which is audited."""
    with pytest.raises(PolicyDenied) as exc_info:
        server.call(
            "read_condition", {"patient": f"Patient/{test_patient_id}"}, actor="session-1", role="assistant"
        )
    assert "not permitted" in str(exc_info.value)

    _actor, actor_role, _action, resource_type, _resource_id, result, reason = latest_audit_row()
    assert result == "deny"
    assert actor_role == "assistant"
    assert resource_type == "Condition"
    assert "not permitted" in reason


def test_assistant_cannot_read_medication_request(server, test_patient_id):
    with pytest.raises(PolicyDenied):
        server.call(
            "read_medication_request",
            {"patient": f"Patient/{test_patient_id}"},
            actor="session-1",
            role="assistant",
        )


def test_unknown_tool_is_denied_and_audited(server, latest_audit_row):
    with pytest.raises(PolicyDenied):
        server.call("delete_everything", {}, actor="session-1", role="assistant")

    *_rest, result, reason = latest_audit_row()
    assert result == "deny"
    assert reason == "unknown tool"


def test_care_team_can_read_condition(server, test_patient_id):
    result = server.call(
        "read_condition", {"patient": f"Patient/{test_patient_id}"}, actor="nurse-1", role="care_team"
    )
    assert result["resourceType"] == "Bundle"


def test_denied_tool_is_not_listed_for_assistant_role(server):
    tools = server.list_tools("assistant")
    names = {t.name for t in tools}
    assert "read_condition" not in names
    assert "read_medication_request" not in names
    assert "search_slots" in names


def test_audit_chain_intact_after_calls():
    result = trustcore.verify_chain()
    assert result.ok, result.reason
