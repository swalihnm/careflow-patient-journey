"""Local, file-based MLflow tracking + registry -- no tracking server needed
at this portfolio scale (SPEC 6.2: "MLflow experiments and registry")."""

import os
import tempfile
from pathlib import Path
from typing import Any

import joblib
import mlflow

MLRUNS_DIR = Path(__file__).resolve().parents[1] / "mlruns"
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"


def use_local_tracking(experiment_name: str) -> None:
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    MLRUNS_DIR.mkdir(parents=True, exist_ok=True)
    # MLflow's plain filesystem store is in maintenance mode as of this version;
    # sqlite is the recommended local (no-server) backend, still just a file.
    db_path = MLRUNS_DIR / "mlflow.db"
    mlflow.set_tracking_uri(f"sqlite:///{db_path.as_posix()}")
    mlflow.set_experiment(experiment_name)


def log_model_joblib(model: Any, model_name: str) -> Path:
    """Logs a fitted model as a joblib artifact under the current MLflow run,
    and saves a copy at ml/artifacts/{model_name}.joblib for the live scoring
    module to load directly (SPEC 6.3) without needing to query MLflow.

    Bypasses mlflow.sklearn.log_model()'s skops-based serialization, which by
    default refuses to (de)serialize LightGBM/CalibratedClassifierCV internals
    as "untrusted types" -- a real safety feature for loading models from
    strangers, not relevant to a model this same run just trained in-process.
    """
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / f"{model_name}.joblib"
    joblib.dump(model, out_path)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / f"{model_name}.joblib"
        joblib.dump(model, tmp_path)
        mlflow.log_artifact(str(tmp_path), artifact_path="model")

    return out_path
