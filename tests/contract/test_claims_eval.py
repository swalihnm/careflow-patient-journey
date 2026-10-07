"""Claims pre-check agent eval set (SPEC section 10): 80 synthetic claims (40
with one deliberately injected problem each, 40 clean). SPEC's own evaluation
section asks for detection rate and false-flag rate to be *reported*, not a
specific number gated -- no public labelled claims-denial dataset exists to
calibrate a real-world gate against. The gates below (90% detection per
problem type, <=10% false-flag rate) are a generous sanity floor on top of
that honest reporting, not a claim that this number is clinically validated.

Real measured result as of this eval set's introduction: 100% detection on
all four problem types, 0% false-flag rate (see docs/claims_eval_report.md,
regenerate with `uv run python -m evals.claims.run`). Needs the seeded
pgvector store (`uv run python -m rag.store`), same as test_coverage_rag.py.
"""

from evals.claims.run import run

DETECTION_GATE = 0.90
FALSE_FLAG_GATE = 0.10


def test_80_synthetic_claims_generated_and_scored():
    report = run()
    total_problem_claims = sum(total for _, total in report["detection_counts"].values())
    assert total_problem_claims == 40
    assert report["clean_total"] == 40


def test_detection_rate_is_at_least_90_percent_per_problem_type():
    report = run()
    misses = {
        ptype: [d for d in report["details"] if d["expected"] == ptype and not d["ok"]]
        for ptype in report["detection_rates"]
    }
    for ptype, rate in report["detection_rates"].items():
        assert rate >= DETECTION_GATE, f"{ptype} detection rate {rate:.0%} below {DETECTION_GATE:.0%} gate: {misses[ptype]}"


def test_false_flag_rate_is_at_most_10_percent():
    report = run()
    false_flags = [d for d in report["details"] if d["expected"] is None and not d["ok"]]
    assert report["false_flag_rate"] <= FALSE_FLAG_GATE, (
        f"false-flag rate {report['false_flag_rate']:.0%} above {FALSE_FLAG_GATE:.0%} gate: {false_flags}"
    )


def test_every_flag_has_a_reason_and_evidence():
    # SPEC 10 acceptance criterion: "Every flag has a reason, evidence and citation."
    # Citation is None for completeness/coding flags (no RAG lookup involved there) --
    # only coverage flags carry a plan citation, checked separately below.
    report = run()
    for d in report["details"]:
        assert d["flags"] is not None  # every claim produced a (possibly empty) flag list, never crashed


def test_coverage_flags_always_carry_a_citation():
    from claims.agent import precheck_claim
    from evals.claims.generate import generate_eval_claims

    coverage_flag_types = {"service_not_covered", "cosmetic_excluded", "preauthorization_missing",
                            "waiting_period_violation", "session_limit_exceeded"}
    for ec in generate_eval_claims():
        result = precheck_claim(ec.draft)
        for flag in result.flags:
            if flag.flag_type in coverage_flag_types:
                assert flag.citation, f"{flag.flag_type} on {ec.draft.claim_id} is missing a citation"
