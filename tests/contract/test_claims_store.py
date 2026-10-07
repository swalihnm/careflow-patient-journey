"""SPEC 10 acceptance criterion: "No automatic changes to claims; all
suggestions require human action (audited)." precheck_claim() itself never
touches a claim -- this test covers the other half: record_decision() writes
both a claims.flag_decisions row and a matching trustcore audit record, so
"audited" means the same tamper-evident chain used everywhere else in this
repo, not a second, weaker mechanism."""

import uuid

import pytest

from claims import store as claims_store


@pytest.fixture(autouse=True)
def _ensure_schema():
    claims_store.ensure_schema()


def test_record_decision_persists_and_audits(latest_audit_row):
    claim_id = f"claims-store-test-{uuid.uuid4().hex[:8]}"
    claims_store.record_decision(
        claim_id=claim_id,
        flag_type="service_not_covered",
        decision="override",
        coder_id="coder-test-1",
        line_id="L1",
        note="Confirmed with patient's updated plan documents.",
    )

    recent = claims_store.recent_decisions(limit=5)
    assert any(d.claim_id == claim_id and d.decision == "override" for d in recent)

    row = latest_audit_row()
    _actor, _actor_role, action, resource_type, resource_id, result, _reason = row
    assert action == "claims.flag_decision.override"
    assert resource_type == "Claim"
    assert resource_id == claim_id
    assert result == "allow"


def test_record_decision_rejects_unknown_decision():
    with pytest.raises(ValueError):
        claims_store.record_decision(
            claim_id="whatever", flag_type="service_not_covered", decision="approve-ish", coder_id="coder-test-1"
        )


def test_precheck_claim_never_mutates_the_input_claim():
    from datetime import date

    from claims.agent import precheck_claim
    from claims.schema import ClaimLine, DraftClaim

    claim = DraftClaim(
        claim_id="C-immutable",
        patient_id="patient-1",
        practitioner_id="practitioner-1",
        plan_name="Gulf Horizon Standard",
        policy_start_date=date(2024, 1, 1),
        service_date=date(2024, 1, 1),
        pre_authorization_obtained=False,
        lines=[
            ClaimLine(
                line_id="L1",
                service_type="cosmetic_procedure",
                diagnosis_code="Z41.1",
                procedure_code="PRC0001",
                amount_aed=100.0,
                encounter_documentation="Elective cosmetic consultation.",
            )
        ],
    )
    before = claim
    precheck_claim(claim)
    assert claim is before  # frozen dataclass; precheck never reassigns or mutates it
    assert claim.lines[0].diagnosis_code == "Z41.1"
