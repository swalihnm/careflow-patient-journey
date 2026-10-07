"""Maps live FHIR resources to each model's feature schema and writes scores
back as FHIR RiskAssessment resources (SPEC 6.3).

Synthea's synthetic histories don't line up 1:1 with the UCI/Kaggle training
schemas (different coding systems, no admission_type/source concept, SNOMED
not ICD-9 diagnoses, ...). Every feature that can't be faithfully derived
gets a documented default, and the RiskAssessment records a confidence score
reflecting how many fields were defaulted -- SPEC 6.3: "Where a feature cannot
be derived from Synthea data, use a documented default and lower the
confidence badge."

This calls the FHIR REST API directly (not through specmcp): specmcp's
allow-list exists to gate the patient-facing LLM assistant (SPEC section 5),
not this internal, system-role batch-scoring job, which -- like the
care-team dashboard -- needs full clinical read access. Every read and every
RiskAssessment write is still audited via trustcore for the same reason.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import joblib
import pandas as pd
import trustcore

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
CONFIDENCE_EXTENSION_URL = "http://careflow.example/fhir/StructureDefinition/feature-confidence"
LOS_POINT_EXTENSION_URL = "http://careflow.example/fhir/StructureDefinition/predicted-los-days"
LOS_INTERVAL_EXTENSION_URL = "http://careflow.example/fhir/StructureDefinition/predicted-los-interval-80"

sys.path.insert(0, str(Path(__file__).resolve().parent / "common"))
from shap_utils import top_drivers, tree_shap_values

# Rough keyword-based grouping of Synthea's SNOMED condition text into the
# same 9 clinical categories the ICD-9 codes were grouped into for training
# (ml/common/icd9_groups.py). Not a certified SNOMED<->ICD-9 crosswalk --
# documented approximation; anything unmatched defaults to "Other" and is
# counted against the confidence score.
CONDITION_KEYWORD_GROUPS = {
    "Diabetes": ["diabet"],
    "Circulatory": ["heart", "hypertension", "cardi", "coronary", "stroke", "circulat"],
    "Respiratory": ["asthma", "bronchi", "pneumonia", "respiratory", "copd", "sinusitis"],
    "Digestive": ["gastro", "digest", "bowel", "liver", "hepat"],
    "Injury": ["fracture", "injury", "wound", "concussion"],
    "Musculoskeletal": ["arthrit", "osteo", "joint", "musculoskeletal", "back pain"],
    "Genitourinary": ["urinary", "kidney", "renal", "prostat"],
    "Neoplasms": ["neoplasm", "cancer", "carcinoma", "tumor"],
}


def _group_condition_text(display: str) -> str:
    text = (display or "").lower()
    for group, keywords in CONDITION_KEYWORD_GROUPS.items():
        if any(kw in text for kw in keywords):
            return group
    return "Other"


class FeatureResult:
    def __init__(self, row: dict[str, Any], defaulted_fields: list[str], total_fields: int):
        self.row = row
        self.defaulted_fields = defaulted_fields
        self.confidence = round(1.0 - len(defaulted_fields) / total_fields, 2) if total_fields else 1.0


def fetch_patient_context(fhir_base_url: str, patient_id: str, actor: str = "scoring-job") -> dict[str, Any]:
    """One audited read per resource type, matching SPEC 5's "every FHIR
    access via specmcp [or, for system jobs, still audited]" rule."""
    with httpx.Client(timeout=30.0) as client:
        patient = client.get(f"{fhir_base_url}/Patient/{patient_id}").json()
        encounters = client.get(f"{fhir_base_url}/Encounter", params={"patient": patient_id, "_count": 50}).json()
        conditions = client.get(f"{fhir_base_url}/Condition", params={"patient": patient_id, "_count": 50}).json()
        medications = client.get(
            f"{fhir_base_url}/MedicationRequest", params={"patient": patient_id, "_count": 50}
        ).json()

    trustcore.record(
        actor=actor, actor_role="system", action="fhir_read", resource_type="Patient",
        resource_id=patient_id, result="allow", reason="feature mapping for risk scoring",
    )

    return {
        "patient": patient,
        "encounters": [e["resource"] for e in encounters.get("entry", [])],
        "conditions": [c["resource"] for c in conditions.get("entry", [])],
        "medications": [m["resource"] for m in medications.get("entry", [])],
    }


def _patient_age(patient: dict) -> float:
    birth_date = patient.get("birthDate")
    if not birth_date:
        return 45.0  # documented default: population median-ish age
    born = datetime.fromisoformat(birth_date)
    now = datetime.now(UTC).replace(tzinfo=None)
    return float((now - born).days / 365.25)


# FHIR's Patient.gender uses lowercase ("male"/"female"/"other"/"unknown"); the
# UCI training data's `gender` column uses "Male"/"Female"/"Unknown/Invalid".
# Real bug found and fixed: the live-scoring mapper used to pass the raw FHIR
# value straight through, which -- being lowercase -- never matched either
# trained category. LightGBM silently treats an unrecognised category as
# missing rather than erroring, so this had been live for a while with no
# visible symptom; confirmed directly that it measurably changes the
# predicted probability for at least one real feature combination (a
# "female" patient scored identically to a "missing gender" one, not to a
# "Female" one). Always map through this function, not `patient["gender"]` directly.
def _map_fhir_gender(fhir_gender: str | None) -> str:
    return {"male": "Male", "female": "Female"}.get(fhir_gender or "", "Unknown/Invalid")


def map_readmission_features(context: dict[str, Any]) -> FeatureResult:
    patient = context["patient"]
    conditions = context["conditions"]
    encounters = context["encounters"]
    defaulted: list[str] = []

    age = _patient_age(patient)
    gender = _map_fhir_gender(patient.get("gender"))
    if gender == "Unknown/Invalid":
        defaulted.append("gender")

    inpatient_count = sum(1 for e in encounters if e.get("class", {}).get("code") in ("IMP", "inpatient"))
    emergency_count = sum(1 for e in encounters if e.get("class", {}).get("code") in ("EMER", "emergency"))
    outpatient_count = sum(1 for e in encounters if e.get("class", {}).get("code") in ("AMB", "ambulatory"))

    if conditions:
        primary_text = conditions[0].get("code", {}).get("text") or conditions[0].get("code", {}).get(
            "coding", [{}]
        )[0].get("display", "")
        diag_1_group = _group_condition_text(primary_text)
        if diag_1_group == "Other":
            defaulted.append("diag_1_group")
    else:
        diag_1_group = "Other"
        defaulted.append("diag_1_group")

    # Not derivable from Synthea's Encounter/Condition shape at all --
    # documented defaults, matching this model's training-time category codes.
    admission_type_id, admission_source_id = 1, 7
    defaulted += ["admission_type_id", "admission_source_id", "race"]

    row = {
        "age_midpoint": age,
        "time_in_hospital": 3,  # documented default (training median-ish); overwritten by a real encounter's length if scoring at discharge
        "num_lab_procedures": 40,
        "num_procedures": 1,
        "num_medications": len(context["medications"]) or 10,
        "number_outpatient": outpatient_count,
        "number_emergency": emergency_count,
        "number_inpatient": inpatient_count,
        "number_diagnoses": max(len(conditions), 1),
        "race": "Other",
        "gender": gender,
        "admission_type_id": admission_type_id,
        "discharge_disposition_id": 1,
        "admission_source_id": admission_source_id,
        "diag_1_group": diag_1_group,
        "diag_2_group": "Other",
        "diag_3_group": "Other",
        "max_glu_serum": "None",
        "A1Cresult": "None",
        "change": "No",
        "diabetesMed": "Yes" if diag_1_group == "Diabetes" else "No",
    }
    defaulted += [
        "time_in_hospital", "num_lab_procedures", "num_procedures", "num_medications",
        "discharge_disposition_id", "diag_2_group", "diag_3_group", "max_glu_serum",
        "A1Cresult", "change",
    ]
    return FeatureResult(row, defaulted, total_fields=len(row))


def score_readmission(fhir_base_url: str, patient_id: str) -> dict[str, Any]:
    context = fetch_patient_context(fhir_base_url, patient_id)
    features = map_readmission_features(context)

    model = joblib.load(ARTIFACTS_DIR / "readmission.joblib")
    X = pd.DataFrame([features.row])
    for col in ["race", "gender", "admission_type_id", "discharge_disposition_id", "admission_source_id",
                "diag_1_group", "diag_2_group", "diag_3_group", "max_glu_serum", "A1Cresult", "change", "diabetesMed"]:
        X[col] = X[col].astype("category")

    probability = float(model.predict_proba(X)[0, 1])

    # SHAP on one of the calibration ensemble's underlying LightGBM boosters,
    # good enough for a per-prediction driver explanation.
    base_estimator = model.calibrated_classifiers_[0].estimator
    shap_row = tree_shap_values(base_estimator, X)[0]
    drivers = top_drivers(list(X.columns), shap_row, X.iloc[0], n=5)

    return {
        "model": "readmission",
        "model_version": "readmission-v1",
        "probability": round(probability, 4),
        "drivers": drivers,
        "confidence": features.confidence,
        "defaulted_fields": features.defaulted_fields,
    }


def map_los_features(context: dict[str, Any]) -> FeatureResult:
    """Same admission-time-only feature set as training (ml/los/features.py)
    -- shares most of its derivation logic with map_readmission_features
    (same context shape), not yet factored into one shared helper (the two
    models' column sets only partially overlap)."""
    patient = context["patient"]
    conditions = context["conditions"]
    encounters = context["encounters"]
    defaulted: list[str] = []

    age = _patient_age(patient)
    gender = _map_fhir_gender(patient.get("gender"))
    if gender == "Unknown/Invalid":
        defaulted.append("gender")

    inpatient_count = sum(1 for e in encounters if e.get("class", {}).get("code") in ("IMP", "inpatient"))
    emergency_count = sum(1 for e in encounters if e.get("class", {}).get("code") in ("EMER", "emergency"))
    outpatient_count = sum(1 for e in encounters if e.get("class", {}).get("code") in ("AMB", "ambulatory"))

    if conditions:
        primary_text = conditions[0].get("code", {}).get("text") or conditions[0].get("code", {}).get(
            "coding", [{}]
        )[0].get("display", "")
        diag_1_group = _group_condition_text(primary_text)
        if diag_1_group == "Other":
            defaulted.append("diag_1_group")
    else:
        diag_1_group = "Other"
        defaulted.append("diag_1_group")

    admission_type_id, admission_source_id = 1, 7
    defaulted += ["admission_type_id", "admission_source_id", "race", "max_glu_serum", "A1Cresult"]

    row = {
        "age_midpoint": age,
        "number_outpatient": outpatient_count,
        "number_emergency": emergency_count,
        "number_inpatient": inpatient_count,
        "race": "Other",
        "gender": gender,
        "admission_type_id": admission_type_id,
        "admission_source_id": admission_source_id,
        "diag_1_group": diag_1_group,
        "max_glu_serum": "None",
        "A1Cresult": "None",
    }
    return FeatureResult(row, defaulted, total_fields=len(row))


def score_los(fhir_base_url: str, patient_id: str) -> dict[str, Any]:
    context = fetch_patient_context(fhir_base_url, patient_id)
    features = map_los_features(context)

    models = joblib.load(ARTIFACTS_DIR / "los.joblib")  # {"point": ..., "lo": ..., "hi": ...} -- see ml/los/train.py
    X = pd.DataFrame([features.row])
    for col in ["race", "gender", "admission_type_id", "admission_source_id", "diag_1_group", "max_glu_serum", "A1Cresult"]:
        X[col] = X[col].astype("category")

    point = float(models["point"].predict(X)[0])
    lo = float(models["lo"].predict(X)[0])
    hi = float(models["hi"].predict(X)[0])

    # point_model is itself a plain LGBMRegressor (not wrapped in a
    # calibration ensemble the way the classifiers are), so SHAP runs on it directly.
    shap_row = tree_shap_values(models["point"], X)[0]
    drivers = top_drivers(list(X.columns), shap_row, X.iloc[0], n=5)

    return {
        "model": "los",
        "model_version": "los-v1",
        "point_days": round(point, 2),
        "interval_80_low_days": round(lo, 2),
        "interval_80_high_days": round(hi, 2),
        "drivers": drivers,
        "confidence": features.confidence,
        "defaulted_fields": features.defaulted_fields,
    }


def fetch_appointment_context(
    fhir_base_url: str, patient_id: str, appointment_id: str, actor: str = "scoring-job"
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        patient = client.get(f"{fhir_base_url}/Patient/{patient_id}").json()
        appointment = client.get(f"{fhir_base_url}/Appointment/{appointment_id}").json()
        conditions = client.get(f"{fhir_base_url}/Condition", params={"patient": patient_id, "_count": 50}).json()

    trustcore.record(
        actor=actor, actor_role="system", action="fhir_read", resource_type="Appointment",
        resource_id=appointment_id, result="allow", reason="feature mapping for no-show risk scoring",
    )

    return {
        "patient": patient,
        "appointment": appointment,
        "conditions": [c["resource"] for c in conditions.get("entry", [])],
    }


def map_noshow_features(context: dict[str, Any]) -> FeatureResult:
    """Maps to ml/noshow/features.py's schema. Several training columns are
    Brazil-specific concepts (Bolsa Familia enrollment, a disability count)
    with no FHIR/UAE equivalent, or reflect a decision (whether a reminder
    was sent) not yet made at scoring time -- all documented defaults below,
    not guesses dressed up as data."""
    patient = context["patient"]
    appointment = context["appointment"]
    conditions = context["conditions"]
    defaulted: list[str] = []

    age = _patient_age(patient)
    fhir_gender = patient.get("gender")
    gender = {"male": "M", "female": "F"}.get(fhir_gender or "")
    if gender is None:
        gender = "F"
        defaulted.append("Gender")

    start = appointment.get("start")
    if not start:
        raise ValueError(f"Appointment/{appointment.get('id')} has no start time -- can't score lead time")
    start_dt = datetime.fromisoformat(start)
    now = datetime.now(UTC)
    lead_time_days = max((start_dt.astimezone(UTC) - now).days, 0)
    appointment_weekday = start_dt.strftime("%A")

    condition_text = " ".join(
        (c.get("code", {}).get("text") or c.get("code", {}).get("coding", [{}])[0].get("display", "")).lower()
        for c in conditions
    )
    hipertension = 1 if any(kw in condition_text for kw in ("hypertension", "high blood pressure")) else 0
    diabetes = 1 if "diabet" in condition_text else 0
    alcoholism = 1 if "alcohol" in condition_text else 0

    # Not derivable from FHIR at all: Scholarship (Bolsa Familia welfare
    # enrollment) and Handcap (a disability count) are Brazil-specific
    # concepts with no UAE/Synthea equivalent; SMS_received reflects a
    # reminder decision made *after* this scoring moment (this is exactly
    # the model the reminder A/B experiment, Phase 5, is meant to drive).
    scholarship, handcap, sms_received = 0, 0, 0
    defaulted += ["Scholarship", "Handcap", "SMS_received"]

    # None of the 81 Brazilian neighbourhoods this model was trained on have
    # any UAE equivalent -- left as a missing categorical (pandas NaN) rather
    # than picking an arbitrary one, which would silently bias the
    # prediction in a specific, unjustified direction.
    neighbourhood = None
    defaulted.append("Neighbourhood")

    row = {
        "lead_time_days": lead_time_days,
        "Age": int(age),
        "Scholarship": scholarship,
        "Hipertension": hipertension,
        "Diabetes": diabetes,
        "Alcoholism": alcoholism,
        "Handcap": handcap,
        "SMS_received": sms_received,
        "Gender": gender,
        "Neighbourhood": neighbourhood,
        "appointment_weekday": appointment_weekday,
    }
    return FeatureResult(row, defaulted, total_fields=len(row))


def score_noshow(fhir_base_url: str, patient_id: str, appointment_id: str) -> dict[str, Any]:
    context = fetch_appointment_context(fhir_base_url, patient_id, appointment_id)
    features = map_noshow_features(context)

    model = joblib.load(ARTIFACTS_DIR / "noshow.joblib")
    X = pd.DataFrame([features.row])
    for col in ["Gender", "Neighbourhood", "appointment_weekday"]:
        X[col] = X[col].astype("category")

    probability = float(model.predict_proba(X)[0, 1])

    base_estimator = model.calibrated_classifiers_[0].estimator
    shap_row = tree_shap_values(base_estimator, X)[0]
    drivers = top_drivers(list(X.columns), shap_row, X.iloc[0], n=5)

    return {
        "model": "noshow",
        "model_version": "noshow-v1",
        "probability": round(probability, 4),
        "drivers": drivers,
        "confidence": features.confidence,
        "defaulted_fields": features.defaulted_fields,
    }


def build_risk_assessment(patient_id: str, score: dict[str, Any], outcome_text: str) -> dict[str, Any]:
    driver_notes = [
        f"{d['feature']}={d['value']} {d['direction']} (SHAP {d['shap']:+.3f})" for d in score["drivers"]
    ]
    return {
        "resourceType": "RiskAssessment",
        "id": f"riskassessment-{score['model']}-{patient_id}",
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "occurrenceDateTime": datetime.now(UTC).isoformat(),
        "method": {"text": score["model_version"]},
        "prediction": [{"outcome": {"text": outcome_text}, "probabilityDecimal": score["probability"]}],
        "note": [
            {"text": f"Model version: {score['model_version']}"},
            {"text": "Top drivers: " + "; ".join(driver_notes)},
            {
                "text": (
                    f"Feature confidence: {score['confidence']} "
                    f"(defaulted: {', '.join(score['defaulted_fields']) or 'none'})"
                )
            },
        ],
        "extension": [{"url": CONFIDENCE_EXTENSION_URL, "valueDecimal": score["confidence"]}],
    }


def build_los_risk_assessment(patient_id: str, score: dict[str, Any]) -> dict[str, Any]:
    """LOS predicts a number of days, not a probability -- FHIR's
    `prediction.probabilityDecimal` doesn't fit, so the point estimate and
    80% interval are carried as extensions (machine-readable) and in `note`
    text (human-readable), the same pattern as the confidence badge."""
    driver_notes = [
        f"{d['feature']}={d['value']} {d['direction']} (SHAP {d['shap']:+.3f})" for d in score["drivers"]
    ]
    return {
        "resourceType": "RiskAssessment",
        "id": f"riskassessment-los-{patient_id}",
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "occurrenceDateTime": datetime.now(UTC).isoformat(),
        "method": {"text": score["model_version"]},
        "prediction": [{"outcome": {"text": "length of stay (days)"}}],
        "note": [
            {"text": f"Model version: {score['model_version']}"},
            {
                "text": (
                    f"Predicted length of stay: {score['point_days']} days "
                    f"(80% interval: {score['interval_80_low_days']}-{score['interval_80_high_days']} days)"
                )
            },
            {"text": "Top drivers: " + "; ".join(driver_notes)},
            {
                "text": (
                    f"Feature confidence: {score['confidence']} "
                    f"(defaulted: {', '.join(score['defaulted_fields']) or 'none'})"
                )
            },
        ],
        "extension": [
            {"url": CONFIDENCE_EXTENSION_URL, "valueDecimal": score["confidence"]},
            {"url": LOS_POINT_EXTENSION_URL, "valueDecimal": score["point_days"]},
            {
                "url": LOS_INTERVAL_EXTENSION_URL,
                "valueRange": {
                    "low": {"value": score["interval_80_low_days"]},
                    "high": {"value": score["interval_80_high_days"]},
                },
            },
        ],
    }


def write_risk_assessment(fhir_base_url: str, patient_id: str, resource: dict[str, Any], actor: str = "scoring-job") -> None:
    with httpx.Client(timeout=30.0) as client:
        resp = client.put(f"{fhir_base_url}/RiskAssessment/{resource['id']}", json=resource)
        resp.raise_for_status()

    trustcore.record(
        actor=actor, actor_role="system", action="write_risk_assessment", resource_type="RiskAssessment",
        resource_id=resource["id"], result="allow", reason=None,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Score one patient's 30-day readmission risk from live FHIR data.")
    parser.add_argument("patient_id")
    parser.add_argument("--base-url", default="http://localhost:8210/fhir")
    args = parser.parse_args()

    result = score_readmission(args.base_url, args.patient_id)
    print(result)
    resource = build_risk_assessment(args.patient_id, result, "30-day readmission")
    write_risk_assessment(args.base_url, args.patient_id, resource)
    print(f"Wrote RiskAssessment/{resource['id']}")
