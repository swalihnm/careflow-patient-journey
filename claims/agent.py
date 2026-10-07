"""SPEC 10 orchestrator: runs the coding, coverage and completeness checks
over a draft claim and returns one flag list. "Output: a risk flag list, each
with reason, evidence and plan citation; a human coder decides" -- this
function never mutates the claim, only returns flags; claims/store.py is
where a human coder's accept/override decision on a flag gets recorded and
audited (SPEC acceptance criterion: "No automatic changes to claims; all
suggestions require human action (audited)")."""

from datetime import date

from claims.coding_check import check_coding
from claims.completeness_check import check_completeness
from claims.coverage_check import check_coverage
from claims.schema import ClaimPrecheckResult, DraftClaim


def precheck_claim(claim: DraftClaim, today: date | None = None) -> ClaimPrecheckResult:
    flags = []
    flags.extend(check_completeness(claim, today=today))
    flags.extend(check_coding(claim.lines))
    flags.extend(check_coverage(claim))
    return ClaimPrecheckResult(claim_id=claim.claim_id, flags=flags)
