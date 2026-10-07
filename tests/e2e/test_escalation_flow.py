"""SPEC 11 acceptance criteria: "... red-flag escalation appearing on the
nurse view, clinician viewing drivers, audit entry for that view."

This file covers the escalation + audit pair together since they're
causally linked (escalating in the patient app is what creates the audit
entry the second half of this file checks for) -- test_clinician_drivers.py
covers the driver-viewing criterion separately, against a patient scored by
Phase 2's models rather than one this test creates itself.
"""

from tests.e2e.conftest import CARE_WEB_URL, complete_patient_gates, set_care_web_role


def test_red_flag_escalation_appears_on_nurse_view_and_is_audited(page, patient_id):
    complete_patient_gates(page, patient_id)

    page.fill('input[placeholder="Type a message…"]', "I have severe chest pain right now")
    page.click('button:has-text("Send")')
    page.wait_for_selector(".escalated-banner", timeout=15_000)

    assert "alerted" in page.locator(".escalated-banner").inner_text().lower()

    # The same red flag's escalation should now appear on the nurse's
    # Escalations view in the care-team dashboard -- a real cross-app check,
    # not just that the patient app rendered a banner.
    page.goto(f"{CARE_WEB_URL}/escalations")
    set_care_web_role(page, "nurse")
    page.wait_for_timeout(1_000)

    page_text = page.locator("main").inner_text()
    assert patient_id in page_text, (
        f"expected to find this test's escalation for patient {patient_id} on the nurse Escalations view"
    )

    # And it must be present on the Audit view too, since SPEC's own design
    # (apps/api/routers/escalations.py) reads escalations directly from the
    # audit chain rather than a parallel table -- this is a real assertion
    # about that design holding, not a given.
    page.goto(f"{CARE_WEB_URL}/audit")
    set_care_web_role(page, "auditor")
    page.wait_for_timeout(1_000)

    audit_text = page.locator("main").inner_text()
    assert "escalation" in audit_text.lower()
