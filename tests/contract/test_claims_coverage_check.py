"""claims/coverage_check.py against the real seeded pgvector store (needs
`uv run python -m rag.store` first, same as test_coverage_rag.py)."""

from datetime import date

from claims.coverage_check import check_coverage
from claims.schema import ClaimLine, DraftClaim

_POLICY_START = date(2024, 1, 1)


def _claim(plan_name: str, line: ClaimLine, service_date=date(2026, 1, 1), pre_authorization_obtained=True) -> DraftClaim:
    return DraftClaim(
        claim_id="C1",
        patient_id="patient-1",
        practitioner_id="practitioner-1",
        plan_name=plan_name,
        policy_start_date=_POLICY_START,
        service_date=service_date,
        pre_authorization_obtained=pre_authorization_obtained,
        lines=[line],
    )


def _line(service_type: str, **overrides) -> ClaimLine:
    defaults = {
        "line_id": "L1",
        "service_type": service_type,
        "diagnosis_code": "J06.9",
        "procedure_code": "PRC0001",
        "amount_aed": 100.0,
        "encounter_documentation": "Patient has a cold.",
    }
    defaults.update(overrides)
    return ClaimLine(**defaults)


def test_covered_service_is_clean():
    claim = _claim("Gulf Horizon Standard", _line("general_practice_visit"))
    assert check_coverage(claim) == []


def test_maternity_not_covered_under_standard_is_flagged():
    claim = _claim("Gulf Horizon Standard", _line("maternity_care", diagnosis_code="Z34.0"))
    flags = check_coverage(claim)
    assert any(f.flag_type == "service_not_covered" and f.citation for f in flags)


def test_maternity_within_waiting_period_is_flagged():
    claim = _claim(
        "Gulf Horizon Plus",
        _line("maternity_care", diagnosis_code="Z34.0"),
        service_date=date(2024, 3, 1),  # 2 months after policy start, Plus requires 10
    )
    flags = check_coverage(claim)
    assert any(f.flag_type == "waiting_period_violation" for f in flags)


def test_maternity_after_waiting_period_is_clean():
    claim = _claim(
        "Gulf Horizon Plus",
        _line("maternity_care", diagnosis_code="Z34.0"),
        service_date=date(2025, 6, 1),  # well past the 10-month waiting period
    )
    assert check_coverage(claim) == []


def test_mri_without_preauthorization_is_flagged():
    claim = _claim("Gulf Horizon Standard", _line("mri_ct_scan", diagnosis_code="M51.2"), pre_authorization_obtained=False)
    flags = check_coverage(claim)
    assert any(f.flag_type == "preauthorization_missing" for f in flags)


def test_mri_with_preauthorization_is_clean():
    claim = _claim("Gulf Horizon Standard", _line("mri_ct_scan", diagnosis_code="M51.2"), pre_authorization_obtained=True)
    assert check_coverage(claim) == []


def test_cosmetic_procedure_always_excluded():
    claim = _claim("Gulf Horizon Family", _line("cosmetic_procedure", diagnosis_code="Z41.1"))
    flags = check_coverage(claim)
    assert any(f.flag_type == "cosmetic_excluded" for f in flags)


def test_emergency_care_exempt_from_preauthorization():
    claim = _claim(
        "Gulf Horizon Standard", _line("emergency_care", diagnosis_code="S06.0"), pre_authorization_obtained=False
    )
    assert check_coverage(claim) == []


def test_family_plan_inherits_uncovered_plus_benefit_via_fallback():
    # Family's own section doesn't restate ordinary visits -- it must fall
    # back to Plus's bullet, not be flagged as "not found under Family".
    claim = _claim("Gulf Horizon Family", _line("specialist_visit", diagnosis_code="I10"))
    assert check_coverage(claim) == []


def test_physiotherapy_session_limit_exceeded_is_flagged():
    claim = _claim(
        "Gulf Horizon Standard",
        _line("physiotherapy_session", diagnosis_code="M54.5", session_number=11),  # Standard limit is 10
    )
    flags = check_coverage(claim)
    assert any(f.flag_type == "session_limit_exceeded" for f in flags)
