"""SPEC 10 step 4: "Completeness check: required fields, valid identifiers,
dates within coverage period." Pure field validation, no RAG/LLM involved."""

from datetime import UTC, date, datetime

from claims.schema import VALID_PLANS, DraftClaim, Flag


def check_completeness(claim: DraftClaim, today: date | None = None) -> list[Flag]:
    today = today or datetime.now(UTC).date()
    flags: list[Flag] = []

    if not claim.patient_id:
        flags.append(Flag("missing_field", "high", "patient_id is required.", "patient_id is empty", None))
    if not claim.practitioner_id:
        flags.append(Flag("missing_field", "high", "practitioner_id is required.", "practitioner_id is empty", None))
    if claim.plan_name not in VALID_PLANS:
        flags.append(
            Flag(
                "invalid_plan",
                "high",
                f"'{claim.plan_name}' is not a recognised plan (expected one of {VALID_PLANS}).",
                f"plan_name={claim.plan_name!r}",
                None,
            )
        )

    if claim.service_date < claim.policy_start_date:
        flags.append(
            Flag(
                "service_before_policy_start",
                "high",
                "Service date is before the policy start date.",
                f"service_date={claim.service_date}, policy_start_date={claim.policy_start_date}",
                None,
            )
        )
    if claim.service_date > today:
        flags.append(
            Flag(
                "service_date_in_future",
                "high",
                "Service date is in the future.",
                f"service_date={claim.service_date}, today={today}",
                None,
            )
        )

    if not claim.lines:
        flags.append(Flag("no_lines", "high", "Claim has no line items.", "lines is empty", None))

    for line in claim.lines:
        if not line.diagnosis_code:
            flags.append(
                Flag("missing_field", "high", f"line {line.line_id}: diagnosis_code is required.", "diagnosis_code is empty", None, line.line_id)
            )
        if not line.procedure_code:
            flags.append(
                Flag("missing_field", "high", f"line {line.line_id}: procedure_code is required.", "procedure_code is empty", None, line.line_id)
            )
        if line.amount_aed <= 0:
            flags.append(
                Flag(
                    "invalid_amount",
                    "high",
                    f"line {line.line_id}: amount_aed must be positive.",
                    f"amount_aed={line.amount_aed}",
                    None,
                    line.line_id,
                )
            )

    return flags
