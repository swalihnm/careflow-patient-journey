"""Regression test for a real PHI-leak bug (SPEC section 8 acceptance
criterion: "No unmasked PHI-like values in logs, automated scan in CI").

assistant/escalate.py used to build the audit log's `reason` field from the
patient's raw, unmasked message (`matched_text=state["message"]` in
assistant/graph.py's escalate_node, passed straight into an f-string).
Confirmed directly against a live Postgres: a message containing a name and
a UAE phone number wrote both verbatim into ops.audit_log.reason, which
apps/api/routers/audit.py's auditor-role masking doesn't touch (it only
masks actor/resource_id). Fixed in assistant/escalate.py's
_safe_masked_reason(); this test is the automated scan SPEC asks for,
covering the actual code path (not just safety/masking.py's masker in
isolation, which tests/unit/test_masking.py already covers).
"""

from trustcore import db as trustcore_db

from assistant.escalate import escalate

PHI_NAME = "Fatima Al Nahyan"
PHI_PHONE = "0501234567"


def test_escalation_audit_reason_never_contains_raw_phi(latest_audit_row):
    trustcore_db.ensure_schema()
    escalate(
        patient_id="phi-masking-regression-test",
        category="chest_pain",
        escalation_type="emergency",
        matched_text=f"This is {PHI_NAME}, phone {PHI_PHONE}, I have severe chest pain right now",
        language="en",
        actor="phi-masking-regression-test-actor",
    )

    row = latest_audit_row()
    reason = row[6]  # (actor, actor_role, action, resource_type, resource_id, result, reason)

    assert PHI_NAME not in reason
    assert PHI_PHONE not in reason
    assert reason is not None and len(reason) > 0  # still a useful audit record, not emptied out


def test_patient_facing_escalation_message_is_unaffected_by_masking():
    # The critical path (what the patient actually sees) must never depend
    # on masking succeeding -- see escalate.py's module docstring.
    result = escalate(
        patient_id="phi-masking-regression-test-2",
        category="suicidal_ideation",
        escalation_type="crisis",
        matched_text="I want to kill myself, my name is Omar",
        language="en",
        actor="phi-masking-regression-test-actor-2",
    )
    assert "998" in result["message"]
    assert "concerned" in result["message"].lower()
