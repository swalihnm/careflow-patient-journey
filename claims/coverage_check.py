"""SPEC 10 step 3: "Coverage check: RAG over the patient's plan: is the
service covered, is pre-authorisation required, are there limits or waiting
periods?"

Reuses the same pgvector-backed retrieval as assistant/coverage.py (genuine
embedding search over rag/corpus/en/insurance_plans.md, nothing hardcoded) --
retrieves the top-k candidates for a plan+service query, then deterministically
selects the chunk whose section name matches the plan (or, when retrieval
can't confidently find one, flags "coverage_undetermined" for human review
rather than guessing -- the same honest low-confidence fallback
assistant/coverage.py already uses). English-only RAG corpus (this module's
English-only, see claims/__init__.py).
"""

import re
from dataclasses import dataclass
from datetime import date

from claims.schema import (
    GENERAL_NOTES_SERVICE_TYPES,
    SERVICE_BULLET_LABEL,
    ClaimLine,
    DraftClaim,
    Flag,
)
from rag.store import RetrievedChunk, query

_DOCUMENT = "insurance_plans"
_GENERAL_SECTION = "General notes that apply to all three plans"
PLAN_FALLBACK = {"Gulf Horizon Family": "Gulf Horizon Plus"}

_PCT_RE = re.compile(r"covered at (\d+)%")
_FULL_RE = re.compile(r"covered in full")
_NOT_COVERED_RE = re.compile(r"not covered")
_PREAUTH_RE = re.compile(r"pre-authorisation required")
_WAITING_RE = re.compile(r"(\d+)-month waiting period")
_SESSION_RE = re.compile(r"up to (\d+) sessions?")

_GENERAL_LABELS = {
    "cosmetic_procedure": "cosmetic procedures",
    "hospital_admission": "hospital admission",
    "emergency_care": "Emergency care",
}


@dataclass(frozen=True)
class CoverageSignals:
    not_covered: bool
    coverage_pct: int | None
    preauth_required: bool
    waiting_period_months: int | None
    session_limit: int | None


def parse_bullet(text: str) -> CoverageSignals:
    pct_match = _PCT_RE.search(text)
    waiting_match = _WAITING_RE.search(text)
    session_match = _SESSION_RE.search(text)
    return CoverageSignals(
        not_covered=bool(_NOT_COVERED_RE.search(text)),
        coverage_pct=int(pct_match.group(1)) if pct_match else (100 if _FULL_RE.search(text) else None),
        preauth_required=bool(_PREAUTH_RE.search(text)),
        waiting_period_months=int(waiting_match.group(1)) if waiting_match else None,
        session_limit=int(session_match.group(1)) if session_match else None,
    )


def _find_line_containing(content: str, substring: str) -> str | None:
    needle = substring.lower()
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("-") and needle in line.lower():
            return line.lstrip("- ").strip()
    return None


def _months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def _citation(chunk: RetrievedChunk) -> str:
    return f"{chunk.document} — {chunk.section} ({chunk.version_date})"


def _retrieve_section(query_text: str, section_name: str, k: int = 8) -> RetrievedChunk | None:
    for result in query(query_text, k=k, language="en"):
        if result.document == _DOCUMENT and result.section == section_name:
            return result
    return None


def _undetermined(line: ClaimLine, detail: str) -> Flag:
    return Flag(
        flag_type="coverage_undetermined",
        severity="medium",
        reason=f"Could not confidently retrieve plan coverage rules for this line ({detail}). Needs human review.",
        evidence=f"line {line.line_id}: service_type={line.service_type}",
        citation=None,
        line_id=line.line_id,
    )


def check_line_coverage(claim: DraftClaim, line: ClaimLine) -> list[Flag]:
    flags: list[Flag] = []

    if line.service_type in GENERAL_NOTES_SERVICE_TYPES:
        chunk = _retrieve_section(
            "general notes pre-authorisation hospital admission emergency care cosmetic procedures "
            "experimental treatments waiting periods",
            _GENERAL_SECTION,
        )
        if chunk is None:
            flags.append(_undetermined(line, "general notes section"))
            return flags

        citation = _citation(chunk)
        label = _GENERAL_LABELS[line.service_type]
        bullet = _find_line_containing(chunk.content, label) or chunk.content

        if line.service_type == "cosmetic_procedure":
            flags.append(
                Flag(
                    "cosmetic_excluded",
                    "high",
                    "Cosmetic procedures are not covered under any Gulf Horizon plan.",
                    bullet,
                    citation,
                    line.line_id,
                )
            )
        elif line.service_type == "hospital_admission" and not claim.pre_authorization_obtained:
            flags.append(
                Flag(
                    "preauthorization_missing",
                    "high",
                    "Pre-authorisation is required for any planned hospital admission.",
                    bullet,
                    citation,
                    line.line_id,
                )
            )
        # emergency_care: covered regardless of pre-authorisation per policy -- no flag.
        return flags

    plan_name = claim.plan_name
    label = SERVICE_BULLET_LABEL.get(line.service_type)
    if label is None:
        flags.append(_undetermined(line, f"unknown service_type {line.service_type!r}"))
        return flags

    chunk = _retrieve_section(f"{plan_name} coverage for {label}", plan_name)
    bullet = _find_line_containing(chunk.content, label) if chunk else None

    # Family's own section only lists what it adds on top of Plus ("Everything
    # in Gulf Horizon Plus, plus: ..."), so a bullet genuinely missing from
    # Family's own chunk doesn't mean the service is uncovered -- it means
    # look at what Family inherits. Retry against the fallback plan's own
    # section before concluding anything about coverage.
    if bullet is None and plan_name in PLAN_FALLBACK:
        fallback_plan = PLAN_FALLBACK[plan_name]
        fallback_chunk = _retrieve_section(f"{fallback_plan} coverage for {label}", fallback_plan)
        fallback_bullet = _find_line_containing(fallback_chunk.content, label) if fallback_chunk else None
        if fallback_bullet is not None:
            plan_name, chunk, bullet = fallback_plan, fallback_chunk, fallback_bullet

    if chunk is None:
        flags.append(_undetermined(line, f"plan section for {claim.plan_name}"))
        return flags

    citation = _citation(chunk)
    if bullet is None:
        flags.append(
            Flag(
                "service_not_covered",
                "high",
                f"No benefit for '{line.service_type}' found under {claim.plan_name}.",
                chunk.content,
                citation,
                line.line_id,
            )
        )
        return flags

    signals = parse_bullet(bullet)

    if signals.not_covered:
        flags.append(Flag("service_not_covered", "high", bullet, bullet, citation, line.line_id))

    if signals.preauth_required and not claim.pre_authorization_obtained:
        flags.append(
            Flag(
                "preauthorization_missing",
                "high",
                f"Pre-authorisation required but not obtained: {bullet}",
                bullet,
                citation,
                line.line_id,
            )
        )

    if signals.waiting_period_months is not None:
        months_since_start = _months_between(claim.policy_start_date, claim.service_date)
        if months_since_start < signals.waiting_period_months:
            flags.append(
                Flag(
                    "waiting_period_violation",
                    "high",
                    f"Service date is {months_since_start} months after policy start; "
                    f"a {signals.waiting_period_months}-month waiting period applies: {bullet}",
                    bullet,
                    citation,
                    line.line_id,
                )
            )

    if signals.session_limit is not None and line.session_number is not None and line.session_number > signals.session_limit:
        flags.append(
            Flag(
                "session_limit_exceeded",
                "medium",
                f"Session #{line.session_number} exceeds the plan's {signals.session_limit}-session "
                f"annual limit: {bullet}",
                bullet,
                citation,
                line.line_id,
            )
        )

    return flags


def check_coverage(claim: DraftClaim) -> list[Flag]:
    flags: list[Flag] = []
    for line in claim.lines:
        flags.extend(check_line_coverage(claim, line))
    return flags
