"""SPEC 10 step 2: "Coding check: compare ICD-10 codes with the encounter
documentation; flag unsupported or missing codes; suggest codes for the
coder to review (never auto-change)."

Deterministic, like the rest of this repo's primary safety/eval mechanisms
(safety/red_flag.py, safety/scope_guard.py) -- no LLM dependency, so results
are exactly reproducible for the synthetic eval set's detection-rate report.
"""

from claims.schema import SERVICE_CATALOG, ClaimLine, Flag


def _matching_keywords(documentation: str, keywords: list[str]) -> bool:
    text = documentation.lower()
    return any(kw in text for kw in keywords)


def suggest_codes(documentation: str) -> list[str]:
    """Candidate ICD-10 codes whose keywords appear in the documentation --
    a suggestion list only, never applied automatically."""
    text = documentation.lower()
    return [code for code, info in SERVICE_CATALOG.items() if any(kw in text for kw in info["keywords"])]


def check_line_coding(line: ClaimLine) -> list[Flag]:
    flags: list[Flag] = []
    info = SERVICE_CATALOG.get(line.diagnosis_code)

    if info is None:
        flags.append(
            Flag(
                flag_type="unknown_code",
                severity="high",
                reason=f"Diagnosis code '{line.diagnosis_code}' is not a recognised code.",
                evidence=f"line {line.line_id}: diagnosis_code={line.diagnosis_code!r}",
                citation=None,
                line_id=line.line_id,
            )
        )
        return flags

    if not _matching_keywords(line.encounter_documentation, info["keywords"]):
        suggestions = suggest_codes(line.encounter_documentation)
        suggestion_text = f" Possible codes to review: {', '.join(suggestions)}." if suggestions else ""
        flags.append(
            Flag(
                flag_type="unsupported_code",
                severity="high",
                reason=(
                    f"Diagnosis code '{line.diagnosis_code}' ({info['label']}) is not substantiated by the "
                    f"encounter documentation.{suggestion_text}"
                ),
                evidence=f"line {line.line_id}: documentation={line.encounter_documentation!r}",
                citation=None,
                line_id=line.line_id,
            )
        )

    if info["service_type"] != line.service_type:
        flags.append(
            Flag(
                flag_type="code_service_mismatch",
                severity="medium",
                reason=(
                    f"Diagnosis code '{line.diagnosis_code}' is normally billed under "
                    f"service type '{info['service_type']}', not '{line.service_type}'."
                ),
                evidence=f"line {line.line_id}: service_type={line.service_type!r}",
                citation=None,
                line_id=line.line_id,
            )
        )

    return flags


def check_coding(lines: list[ClaimLine]) -> list[Flag]:
    flags: list[Flag] = []
    for line in lines:
        flags.extend(check_line_coding(line))
    return flags
