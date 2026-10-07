"""Draft claim data model + the synthetic ICD-10 service catalog shared by
claims/coding_check.py and evals/claims/generate.py (one definition, so the
eval generator can't drift from what the coding check actually knows about).

A real claims pipeline would derive diagnosis/procedure codes from FHIR
Encounter/Condition resources during coding. This module takes the
already-coded draft claim as input instead (matching FHIR's own Claim
resource, which carries its own diagnosisCodeableConcept array rather than a
live reference) -- deliberately: it means this stretch module never needs to
read Condition or MedicationRequest, keeping it well clear of CLAUDE.md's
"Assistant tools cannot read Condition or MedicationRequest" boundary (this
isn't the patient assistant, but there's no reason to go near that line for a
module that doesn't need to).
"""

from dataclasses import dataclass, field
from datetime import date

VALID_PLANS = ("Gulf Horizon Standard", "Gulf Horizon Plus", "Gulf Horizon Family")

# service_type -> (label used in the insurance_plans.md bullet text, a short
# set of documentation keywords that should appear if this diagnosis code is
# genuinely supported by the encounter note). Codes are synthetic but
# ICD-10-shaped, matching this repo's "synthetic/de-identified only" rule.
SERVICE_CATALOG: dict[str, dict] = {
    "J06.9": {
        "label": "acute upper respiratory infection",
        "service_type": "general_practice_visit",
        "keywords": ["cold", "flu", "upper respiratory", "cough", "sore throat", "congestion"],
    },
    "I10": {
        "label": "essential hypertension",
        "service_type": "specialist_visit",
        "keywords": ["hypertension", "blood pressure", "bp "],
    },
    "M54.5": {
        "label": "low back pain",
        "service_type": "physiotherapy_session",
        "keywords": ["back pain", "lower back", "lumbar"],
    },
    "S93.4": {
        "label": "ankle sprain",
        "service_type": "diagnostic_imaging",
        "keywords": ["sprain", "ankle", "twisted"],
    },
    "M51.2": {
        "label": "lumbar disc disorder",
        "service_type": "mri_ct_scan",
        "keywords": ["disc", "herniation", "spine", "radiculopathy"],
    },
    "Z34.0": {
        "label": "normal pregnancy supervision",
        "service_type": "maternity_care",
        "keywords": ["pregnan", "prenatal", "antenatal", "obstetric"],
    },
    "K02.9": {
        "label": "dental caries",
        "service_type": "dental_care",
        "keywords": ["cavity", "tooth", "dental", "decay"],
    },
    "H52.1": {
        "label": "myopia",
        "service_type": "vision_care",
        "keywords": ["vision", "eye", "refraction", "myopia", "glasses"],
    },
    "Z00.129": {
        "label": "routine child health exam",
        "service_type": "paediatric_visit",
        "keywords": ["well-child", "child health", "checkup", "vaccination", "growth"],
    },
    "Z41.1": {
        "label": "cosmetic surgery, not elsewhere classified",
        "service_type": "cosmetic_procedure",
        "keywords": ["cosmetic", "aesthetic", "elective"],
    },
    "J18.9": {
        "label": "pneumonia, unspecified organism",
        "service_type": "hospital_admission",
        "keywords": ["pneumonia", "admitted", "inpatient", "hospitalised", "hospitalized"],
    },
    "S06.0": {
        "label": "concussion",
        "service_type": "emergency_care",
        "keywords": ["emergency", "trauma", "accident", "concussion", "head injury"],
    },
}

# service_type -> the literal bullet label substring in rag/corpus/en/insurance_plans.md,
# used to find the right line inside a retrieved plan-section chunk.
SERVICE_BULLET_LABEL: dict[str, str] = {
    "general_practice_visit": "General practice and family medicine visits",
    "specialist_visit": "Specialist visits",
    "physiotherapy_session": "Physiotherapy",
    "diagnostic_imaging": "Diagnostic imaging",
    "mri_ct_scan": "MRI/CT scans",
    "maternity_care": "Maternity care",
    "dental_care": "Dental and vision",
    "vision_care": "Dental and vision",
    "paediatric_visit": "Paediatric visits",
}
# service types resolved against the corpus's "General notes" section instead
# of a specific plan section (cross-cutting rules, not plan-specific bullets).
GENERAL_NOTES_SERVICE_TYPES = {"cosmetic_procedure", "hospital_admission", "emergency_care"}


@dataclass(frozen=True)
class ClaimLine:
    line_id: str
    service_type: str
    diagnosis_code: str
    procedure_code: str
    amount_aed: float
    encounter_documentation: str
    session_number: int | None = None  # for physiotherapy_session: which session this year


@dataclass(frozen=True)
class DraftClaim:
    claim_id: str
    patient_id: str
    practitioner_id: str
    plan_name: str
    policy_start_date: date
    service_date: date
    pre_authorization_obtained: bool
    lines: list[ClaimLine] = field(default_factory=list)


@dataclass(frozen=True)
class Flag:
    flag_type: str
    severity: str  # "high" | "medium" | "low"
    reason: str
    evidence: str
    citation: str | None
    line_id: str | None = None


@dataclass(frozen=True)
class ClaimPrecheckResult:
    claim_id: str
    flags: list[Flag]

    @property
    def clean(self) -> bool:
        return not self.flags
