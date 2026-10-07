from claims.coding_check import check_line_coding, suggest_codes
from claims.schema import ClaimLine


def _line(diagnosis_code: str, documentation: str, service_type: str = "general_practice_visit") -> ClaimLine:
    return ClaimLine(
        line_id="L1",
        service_type=service_type,
        diagnosis_code=diagnosis_code,
        procedure_code="PRC0001",
        amount_aed=100.0,
        encounter_documentation=documentation,
    )


def test_known_code_with_supporting_documentation_is_clean():
    line = _line("J06.9", "Patient has a cough and sore throat, consistent with a cold.")
    assert check_line_coding(line) == []


def test_unknown_code_is_flagged():
    line = _line("X99.9", "Some documentation.")
    flags = check_line_coding(line)
    assert len(flags) == 1
    assert flags[0].flag_type == "unknown_code"


def test_known_code_without_supporting_documentation_is_flagged():
    line = _line("J06.9", "Patient seen for routine administrative paperwork review.")
    flags = check_line_coding(line)
    assert any(f.flag_type == "unsupported_code" for f in flags)


def test_code_service_type_mismatch_is_flagged():
    line = _line("J06.9", "Patient has a cold.", service_type="mri_ct_scan")
    flags = check_line_coding(line)
    assert any(f.flag_type == "code_service_mismatch" for f in flags)


def test_suggest_codes_finds_plausible_candidates():
    suggestions = suggest_codes("Patient reports persistent lower back pain.")
    assert "M54.5" in suggestions
