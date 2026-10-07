"""Confirms tool generation is purely data-driven from the real repo files
(fhir/openapi/fhir.yaml x fhir/policies/fhir.yaml), not hand-written per tool."""

from specmcp.generator import build_registry


def test_registry_only_contains_policy_controlled_operations():
    registry = build_registry()
    assert "read_condition" in registry
    assert "read_medication_request" in registry
    # every operation in the registry came from a policy entry with a resource
    for tool in registry.values():
        assert tool.resource


def test_assistant_role_excluded_from_clinical_reads():
    registry = build_registry()
    assert "assistant" not in registry["read_condition"].allowed_roles
    assert "assistant" not in registry["read_medication_request"].allowed_roles


def test_assistant_role_included_for_booking_and_coverage():
    registry = build_registry()
    for tool_name in [
        "search_slots",
        "book_appointment",
        "cancel_appointment",
        "search_appointments",
        "read_slot",
        "update_slot",
        "read_patient_demographics",
        "read_coverage",
        "write_questionnaire_response",
        "write_communication",
    ]:
        assert "assistant" in registry[tool_name].allowed_roles, tool_name


def test_path_and_query_params_extracted():
    registry = build_registry()
    read_patient = registry["read_patient_demographics"]
    assert read_patient.path_params == ["id"]
    read_coverage = registry["read_coverage"]
    assert "beneficiary" in read_coverage.query_params


def test_unlisted_operation_is_not_exposed():
    # /Slot's GET is search_slots, but there's no operation for, say, deleting a Slot
    # anywhere in the openapi file at all -- nothing to assert by name, so just check
    # the registry doesn't contain anything unexpected beyond the policy's operations.
    registry = build_registry()
    assert set(registry.keys()) == {
        "search_slots",
        "book_appointment",
        "cancel_appointment",
        "search_appointments",
        "read_slot",
        "update_slot",
        "read_patient_demographics",
        "read_coverage",
        "write_questionnaire_response",
        "write_communication",
        "read_condition",
        "read_medication_request",
    }
