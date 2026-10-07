"""One mock insurer + 3 mock plans, and a Coverage resource per patient.

The plans here are just identifiers/names for the FHIR record to point at;
the actual coverage-table content patients ask the assistant about (SPEC
section 3, "Clinic policies and insurer plans") is authored separately as
RAG documents in a later phase.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from idhash import bucket

PAYER_ORG_ID = "org-gulf-horizon-insurance"

PLANS = [
    {"id": "plan-standard", "name": "Gulf Horizon Standard"},
    {"id": "plan-plus", "name": "Gulf Horizon Plus"},
    {"id": "plan-family", "name": "Gulf Horizon Family"},
]


def build_payer_organization() -> dict:
    return {
        "resourceType": "Organization",
        "id": PAYER_ORG_ID,
        "active": True,
        "name": "Gulf Horizon Insurance",
        "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type", "code": "ins"}]}],
    }


def build_insurance_plans() -> list[dict]:
    return [
        {
            "resourceType": "InsurancePlan",
            "id": plan["id"],
            "status": "active",
            "name": plan["name"],
            "ownedBy": {"reference": f"Organization/{PAYER_ORG_ID}"},
        }
        for plan in PLANS
    ]


def build_coverage_for_patient(patient_id: str) -> dict:
    plan = PLANS[bucket(patient_id, len(PLANS))]
    return {
        "resourceType": "Coverage",
        "id": f"coverage-{patient_id}",
        "status": "active",
        "beneficiary": {"reference": f"Patient/{patient_id}"},
        "payor": [{"reference": f"Organization/{PAYER_ORG_ID}"}],
        "class": [
            {
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/coverage-class", "code": "plan"}]},
                "value": plan["id"],
                "name": plan["name"],
            }
        ],
    }
