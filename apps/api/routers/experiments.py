"""GET /v1/experiments/{id}/report (SPEC 9): the reminder A/B report.

Serves the report `ml/experiment/run.py` already generated to
docs/experiment_report.md rather than re-running the simulation per request
-- re-running would draw fresh random outcomes each call, giving a different
"result" on every page load, which isn't what a report page means.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from apps.api.dependencies import require_role

router = APIRouter()

REPORT_PATH = Path(__file__).resolve().parents[3] / "docs" / "experiment_report.md"
KNOWN_EXPERIMENT_IDS = {"reminder-ab-v1"}


@router.get("/v1/experiments/{experiment_id}/report")
def experiment_report(experiment_id: str, role: str = Depends(require_role("admin", "clinician"))):
    if experiment_id not in KNOWN_EXPERIMENT_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown experiment id '{experiment_id}'")
    if not REPORT_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="No report generated yet -- run `uv run python -m ml.experiment.run` first.",
        )

    return {
        "experiment_id": experiment_id,
        "generated_at": REPORT_PATH.stat().st_mtime,
        "report_markdown": REPORT_PATH.read_text(encoding="utf-8"),
        "role": role,
    }
