from datetime import date

from claims.completeness_check import check_completeness
from claims.schema import ClaimLine, DraftClaim


def _claim(**overrides) -> DraftClaim:
    defaults = {
        "claim_id": "C1",
        "patient_id": "patient-1",
        "practitioner_id": "practitioner-1",
        "plan_name": "Gulf Horizon Standard",
        "policy_start_date": date(2024, 1, 1),
        "service_date": date(2024, 6, 1),
        "pre_authorization_obtained": False,
        "lines": [
            ClaimLine(
                line_id="L1",
                service_type="general_practice_visit",
                diagnosis_code="J06.9",
                procedure_code="PRC0001",
                amount_aed=100.0,
                encounter_documentation="Patient has a cold.",
            )
        ],
    }
    defaults.update(overrides)
    return DraftClaim(**defaults)


def test_well_formed_claim_is_clean():
    assert check_completeness(_claim(), today=date(2026, 1, 1)) == []


def test_missing_patient_id_is_flagged():
    flags = check_completeness(_claim(patient_id=""), today=date(2026, 1, 1))
    assert any(f.flag_type == "missing_field" for f in flags)


def test_invalid_plan_is_flagged():
    flags = check_completeness(_claim(plan_name="Not A Real Plan"), today=date(2026, 1, 1))
    assert any(f.flag_type == "invalid_plan" for f in flags)


def test_service_before_policy_start_is_flagged():
    flags = check_completeness(
        _claim(policy_start_date=date(2024, 6, 1), service_date=date(2024, 1, 1)), today=date(2026, 1, 1)
    )
    assert any(f.flag_type == "service_before_policy_start" for f in flags)


def test_service_date_in_future_is_flagged():
    flags = check_completeness(_claim(service_date=date(2030, 1, 1)), today=date(2026, 1, 1))
    assert any(f.flag_type == "service_date_in_future" for f in flags)


def test_no_lines_is_flagged():
    flags = check_completeness(_claim(lines=[]), today=date(2026, 1, 1))
    assert any(f.flag_type == "no_lines" for f in flags)


def test_non_positive_amount_is_flagged():
    line = ClaimLine(
        line_id="L1",
        service_type="general_practice_visit",
        diagnosis_code="J06.9",
        procedure_code="PRC0001",
        amount_aed=0.0,
        encounter_documentation="Patient has a cold.",
    )
    flags = check_completeness(_claim(lines=[line]), today=date(2026, 1, 1))
    assert any(f.flag_type == "invalid_amount" for f in flags)
