"""GET /v1/qa/overview (SPEC 9): QA judge scores, failure tags, trends.

Also carries recent eval-set run history (SPEC 11: "nightly live run;
results in ops.eval_runs and the Quality dashboard") -- one endpoint for
the Quality view rather than a second one just for eval runs.
"""

from dataclasses import asdict

from fastapi import APIRouter, Depends

from apps.api.dependencies import require_role
from evals.store import recent_runs
from qa.store import overview

router = APIRouter()


@router.get("/v1/qa/overview")
def qa_overview(role: str = Depends(require_role("admin", "clinician"))):
    return {**overview(), "recent_eval_runs": [asdict(r) for r in recent_runs()], "role": role}
