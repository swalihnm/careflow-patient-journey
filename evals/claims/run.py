"""Runs the claims pre-check agent over the 80-claim synthetic eval set
(evals/claims/generate.py) and reports detection rate per injected-problem
type plus the false-flag rate on the 40 clean claims -- SPEC 10's own
"evaluation (honest version)" section, which deliberately asks for this to
be reported, not gated at a specific number (no public labelled claims-denial
dataset exists to calibrate a gate against)."""

from collections import defaultdict
from pathlib import Path

from claims.agent import precheck_claim
from evals.claims.generate import generate_eval_claims

REPO_ROOT = Path(__file__).resolve().parents[2]

_WRONG_CODE_TYPES = {"unknown_code", "unsupported_code"}
_UNCOVERED_TYPES = {"service_not_covered", "cosmetic_excluded"}
_PROBLEM_FLAG_TYPES = {
    "wrong_code": _WRONG_CODE_TYPES,
    "uncovered_service": _UNCOVERED_TYPES,
    "missing_preauth": {"preauthorization_missing"},
    "waiting_period_violation": {"waiting_period_violation"},
}


def run() -> dict:
    eval_claims = generate_eval_claims()

    detections: dict[str, list[bool]] = defaultdict(list)
    false_flags = 0
    clean_total = 0
    details = []

    for ec in eval_claims:
        result = precheck_claim(ec.draft)
        flag_types = {f.flag_type for f in result.flags}

        if ec.expected_problem is None:
            clean_total += 1
            flagged = bool(flag_types)
            if flagged:
                false_flags += 1
            details.append(
                {"claim_id": ec.draft.claim_id, "expected": None, "flags": sorted(flag_types), "ok": not flagged}
            )
        else:
            expected_types = _PROBLEM_FLAG_TYPES[ec.expected_problem]
            detected = bool(flag_types & expected_types)
            detections[ec.expected_problem].append(detected)
            details.append(
                {
                    "claim_id": ec.draft.claim_id,
                    "expected": ec.expected_problem,
                    "flags": sorted(flag_types),
                    "ok": detected,
                }
            )

    detection_rates = {ptype: sum(hits) / len(hits) for ptype, hits in detections.items()}
    false_flag_rate = false_flags / clean_total if clean_total else 0.0

    return {
        "detection_rates": detection_rates,
        "detection_counts": {k: (sum(v), len(v)) for k, v in detections.items()},
        "false_flag_rate": false_flag_rate,
        "false_flags": false_flags,
        "clean_total": clean_total,
        "details": details,
    }


def _print_report(report: dict) -> str:
    lines = ["# Claims pre-check agent -- synthetic eval report", ""]
    lines.append(
        "Demonstration only (SPEC 10): detection of *deliberately injected* problems in synthetic claims, "
        "not real-world denial prediction -- no public labelled claims-denial dataset exists to calibrate "
        "against real outcomes."
    )
    lines.append("")
    lines.append("## Detection rate per problem type")
    lines.append("")
    lines.append("| Problem type | Detected | Rate |")
    lines.append("| --- | --- | --- |")
    for ptype, (hits, total) in report["detection_counts"].items():
        lines.append(f"| {ptype} | {hits}/{total} | {hits / total:.0%} |")
    lines.append("")
    lines.append("## False-flag rate (on 40 clean claims)")
    lines.append("")
    lines.append(f"{report['false_flags']}/{report['clean_total']} clean claims raised at least one flag "
                 f"({report['false_flag_rate']:.0%} false-flag rate).")
    lines.append("")
    return "\n".join(lines)


def run_and_write_report(out_path: Path | None = None) -> dict:
    report = run()
    out_path = out_path or REPO_ROOT / "docs" / "claims_eval_report.md"
    out_path.write_text(_print_report(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    import sys

    report = run_and_write_report()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(_print_report(report))
