"""SPEC 10 evaluation: "Create 40 synthetic claims with deliberately injected
problems (wrong code, uncovered service, missing pre-authorisation, expired
coverage) plus 40 clean ones; report detection rate per problem type and
false-flag rate."

Every "clean" claim is built from a (plan, service_type) combination that is
genuinely covered per rag/corpus/en/insurance_plans.md -- checked by hand
against that file, not assumed. Problem claims start from a clean claim and
mutate exactly one thing, so each one has exactly one expected problem type.
"""

from dataclasses import dataclass
from datetime import date

from claims.schema import ClaimLine, DraftClaim

DOC_TEMPLATES: dict[str, list[str]] = {
    "J06.9": [
        "Patient presents with cough and sore throat for 3 days, consistent with a cold.",
        "Follow-up for ongoing flu-like symptoms and nasal congestion.",
    ],
    "I10": [
        "Routine specialist review of persistently elevated blood pressure (hypertension).",
        "Follow-up visit to monitor hypertension control.",
    ],
    "M54.5": [
        "Physiotherapy session for chronic lower back pain.",
        "Continued treatment for lumbar back pain following initial assessment.",
    ],
    "S93.4": [
        "X-ray ordered after patient twisted their ankle during sport; suspected sprain.",
        "Ultrasound imaging for persistent ankle sprain symptoms.",
    ],
    "M51.2": [
        "MRI requested to evaluate suspected lumbar disc herniation with radiculopathy.",
        "Follow-up MRI for known disc herniation of the spine.",
    ],
    "Z34.0": [
        "Routine antenatal check, normal pregnancy progressing well.",
        "Prenatal visit, 20-week pregnancy supervision.",
    ],
    "K02.9": [
        "Dental exam found early-stage tooth decay (cavity) requiring a filling.",
        "Follow-up for dental caries treatment.",
    ],
    "H52.1": [
        "Eye exam confirms myopia; new glasses prescription issued.",
        "Follow-up vision assessment for known myopia.",
    ],
    "Z00.129": [
        "Routine well-child checkup including growth assessment and vaccination.",
        "Annual child health exam with vaccination update.",
    ],
    "Z41.1": [
        "Consultation for an elective cosmetic procedure requested by the patient.",
        "Follow-up for an aesthetic cosmetic treatment.",
    ],
    "J18.9": [
        "Patient admitted as inpatient with pneumonia, started on IV antibiotics.",
        "Continued inpatient care for hospitalised pneumonia case.",
    ],
    "S06.0": [
        "Emergency department visit after a head injury with suspected concussion from an accident.",
        "Emergency trauma assessment following an accident.",
    ],
}

UNRELATED_DOC = "Patient seen for routine administrative paperwork review; no clinical complaints discussed."

# (plan, service_type, diagnosis_code, needs_preauth, session_number, months_after_policy_start)
_CLEAN_COMBOS: list[tuple[str, str, str, bool, int | None, int]] = [
    ("Gulf Horizon Standard", "general_practice_visit", "J06.9", False, None, 24),
    ("Gulf Horizon Standard", "specialist_visit", "I10", False, None, 24),
    ("Gulf Horizon Standard", "physiotherapy_session", "M54.5", False, 1, 24),
    ("Gulf Horizon Standard", "diagnostic_imaging", "S93.4", False, None, 24),
    ("Gulf Horizon Standard", "mri_ct_scan", "M51.2", True, None, 24),
    ("Gulf Horizon Standard", "emergency_care", "S06.0", False, None, 24),
    ("Gulf Horizon Standard", "hospital_admission", "J18.9", True, None, 24),
    ("Gulf Horizon Plus", "general_practice_visit", "J06.9", False, None, 24),
    ("Gulf Horizon Plus", "specialist_visit", "I10", False, None, 24),
    ("Gulf Horizon Plus", "physiotherapy_session", "M54.5", False, 1, 24),
    ("Gulf Horizon Plus", "diagnostic_imaging", "S93.4", False, None, 24),
    ("Gulf Horizon Plus", "mri_ct_scan", "M51.2", True, None, 24),
    ("Gulf Horizon Plus", "maternity_care", "Z34.0", False, None, 14),
    ("Gulf Horizon Plus", "dental_care", "K02.9", False, None, 24),
    ("Gulf Horizon Plus", "vision_care", "H52.1", False, None, 24),
    ("Gulf Horizon Plus", "emergency_care", "S06.0", False, None, 24),
    ("Gulf Horizon Plus", "hospital_admission", "J18.9", True, None, 24),
    ("Gulf Horizon Family", "general_practice_visit", "J06.9", False, None, 24),
    ("Gulf Horizon Family", "specialist_visit", "I10", False, None, 24),
    ("Gulf Horizon Family", "physiotherapy_session", "M54.5", False, 1, 24),
    ("Gulf Horizon Family", "diagnostic_imaging", "S93.4", False, None, 24),
    ("Gulf Horizon Family", "mri_ct_scan", "M51.2", True, None, 24),
    ("Gulf Horizon Family", "maternity_care", "Z34.0", False, None, 10),
    ("Gulf Horizon Family", "dental_care", "K02.9", False, None, 24),
    ("Gulf Horizon Family", "vision_care", "H52.1", False, None, 24),
    ("Gulf Horizon Family", "paediatric_visit", "Z00.129", False, None, 24),
    ("Gulf Horizon Family", "emergency_care", "S06.0", False, None, 24),
    ("Gulf Horizon Family", "hospital_admission", "J18.9", True, None, 24),
]

_POLICY_START = date(2024, 1, 1)


def _service_date(months_after_start: int) -> date:
    year = _POLICY_START.year + (_POLICY_START.month - 1 + months_after_start) // 12
    month = (_POLICY_START.month - 1 + months_after_start) % 12 + 1
    return date(year, month, min(_POLICY_START.day, 28))


@dataclass(frozen=True)
class EvalClaim:
    draft: DraftClaim
    expected_problem: str | None  # None = clean; else "wrong_code" | "uncovered_service" | "missing_preauth" | "waiting_period_violation"


def _make_clean(i: int, combo: tuple, doc_variant: int) -> EvalClaim:
    plan, service_type, code, needs_preauth, session_number, months_after = combo
    doc = DOC_TEMPLATES[code][doc_variant % len(DOC_TEMPLATES[code])]
    claim = DraftClaim(
        claim_id=f"clean-{i:03d}",
        patient_id=f"eval-patient-{i:03d}",
        practitioner_id=f"eval-practitioner-{i % 5:03d}",
        plan_name=plan,
        policy_start_date=_POLICY_START,
        service_date=_service_date(months_after),
        pre_authorization_obtained=needs_preauth,
        lines=[
            ClaimLine(
                line_id=f"clean-{i:03d}-L1",
                service_type=service_type,
                diagnosis_code=code,
                procedure_code=f"PRC{i:04d}",
                amount_aed=250.0 + i,
                encounter_documentation=doc,
                session_number=session_number,
            )
        ],
    )
    return EvalClaim(draft=claim, expected_problem=None)


def _mutate_wrong_code(i: int, base: EvalClaim, unknown: bool) -> EvalClaim:
    line = base.draft.lines[0]
    if unknown:
        new_line = ClaimLine(
            line_id=line.line_id,
            service_type=line.service_type,
            diagnosis_code="X99.9",
            procedure_code=line.procedure_code,
            amount_aed=line.amount_aed,
            encounter_documentation=line.encounter_documentation,
            session_number=line.session_number,
        )
    else:
        new_line = ClaimLine(
            line_id=line.line_id,
            service_type=line.service_type,
            diagnosis_code=line.diagnosis_code,
            procedure_code=line.procedure_code,
            amount_aed=line.amount_aed,
            encounter_documentation=UNRELATED_DOC,
            session_number=line.session_number,
        )
    claim = DraftClaim(
        claim_id=f"wrongcode-{i:03d}",
        patient_id=base.draft.patient_id,
        practitioner_id=base.draft.practitioner_id,
        plan_name=base.draft.plan_name,
        policy_start_date=base.draft.policy_start_date,
        service_date=base.draft.service_date,
        pre_authorization_obtained=base.draft.pre_authorization_obtained,
        lines=[new_line],
    )
    return EvalClaim(draft=claim, expected_problem="wrong_code")


def _mutate_uncovered(i: int, plan: str, variant: str) -> EvalClaim:
    if variant == "cosmetic":
        service_type, code = "cosmetic_procedure", "Z41.1"
    elif variant == "maternity_under_standard":
        service_type, code, plan = "maternity_care", "Z34.0", "Gulf Horizon Standard"
    else:  # dental_under_standard
        service_type, code, plan = "dental_care", "K02.9", "Gulf Horizon Standard"
    doc = DOC_TEMPLATES[code][0]
    claim = DraftClaim(
        claim_id=f"uncovered-{i:03d}",
        patient_id=f"eval-patient-u{i:03d}",
        practitioner_id=f"eval-practitioner-{i % 5:03d}",
        plan_name=plan,
        policy_start_date=_POLICY_START,
        service_date=_service_date(24),
        pre_authorization_obtained=True,
        lines=[
            ClaimLine(
                line_id=f"uncovered-{i:03d}-L1",
                service_type=service_type,
                diagnosis_code=code,
                procedure_code=f"PRC{i:04d}",
                amount_aed=300.0 + i,
                encounter_documentation=doc,
            )
        ],
    )
    return EvalClaim(draft=claim, expected_problem="uncovered_service")


def _mutate_missing_preauth(i: int, plan: str, service_type: str, code: str) -> EvalClaim:
    doc = DOC_TEMPLATES[code][0]
    claim = DraftClaim(
        claim_id=f"preauth-{i:03d}",
        patient_id=f"eval-patient-p{i:03d}",
        practitioner_id=f"eval-practitioner-{i % 5:03d}",
        plan_name=plan,
        policy_start_date=_POLICY_START,
        service_date=_service_date(24),
        pre_authorization_obtained=False,
        lines=[
            ClaimLine(
                line_id=f"preauth-{i:03d}-L1",
                service_type=service_type,
                diagnosis_code=code,
                procedure_code=f"PRC{i:04d}",
                amount_aed=400.0 + i,
                encounter_documentation=doc,
            )
        ],
    )
    return EvalClaim(draft=claim, expected_problem="missing_preauth")


def _mutate_waiting_period(i: int, plan: str, months_after: int) -> EvalClaim:
    doc = DOC_TEMPLATES["Z34.0"][0]
    claim = DraftClaim(
        claim_id=f"waiting-{i:03d}",
        patient_id=f"eval-patient-w{i:03d}",
        practitioner_id=f"eval-practitioner-{i % 5:03d}",
        plan_name=plan,
        policy_start_date=_POLICY_START,
        service_date=_service_date(months_after),
        pre_authorization_obtained=True,
        lines=[
            ClaimLine(
                line_id=f"waiting-{i:03d}-L1",
                service_type="maternity_care",
                diagnosis_code="Z34.0",
                procedure_code=f"PRC{i:04d}",
                amount_aed=500.0 + i,
                encounter_documentation=doc,
            )
        ],
    )
    return EvalClaim(draft=claim, expected_problem="waiting_period_violation")


def generate_eval_claims() -> list[EvalClaim]:
    clean: list[EvalClaim] = []
    for i, combo in enumerate(_CLEAN_COMBOS):
        clean.append(_make_clean(i, combo, doc_variant=0))
    # repeat the first 12 combos with a second documentation wording + a
    # different patient/amount to reach exactly 40 clean claims.
    for j, combo in enumerate(_CLEAN_COMBOS[:12]):
        clean.append(_make_clean(len(_CLEAN_COMBOS) + j, combo, doc_variant=1))
    assert len(clean) == 40, len(clean)

    wrong_code = [_mutate_wrong_code(i, clean[i], unknown=(i % 2 == 0)) for i in range(10)]

    uncovered_variants = (["cosmetic"] * 4 + ["maternity_under_standard"] * 3 + ["dental_under_standard"] * 3)
    uncovered = [
        _mutate_uncovered(i, plan="Gulf Horizon Standard", variant=v) for i, v in enumerate(uncovered_variants)
    ]

    preauth_specs = (
        [("Gulf Horizon Standard", "mri_ct_scan", "M51.2")] * 2
        + [("Gulf Horizon Plus", "mri_ct_scan", "M51.2")] * 2
        + [("Gulf Horizon Family", "mri_ct_scan", "M51.2")] * 2
        + [("Gulf Horizon Standard", "hospital_admission", "J18.9")] * 2
        + [("Gulf Horizon Plus", "hospital_admission", "J18.9")] * 1
        + [("Gulf Horizon Family", "hospital_admission", "J18.9")] * 1
    )
    missing_preauth = [_mutate_missing_preauth(i, plan, svc, code) for i, (plan, svc, code) in enumerate(preauth_specs)]

    waiting_specs = [("Gulf Horizon Plus", m) for m in (1, 3, 5, 7, 9)] + [
        ("Gulf Horizon Family", m) for m in (1, 2, 3, 4, 5)
    ]
    waiting = [_mutate_waiting_period(i, plan, months) for i, (plan, months) in enumerate(waiting_specs)]

    problems = wrong_code + uncovered + missing_preauth + waiting
    assert len(problems) == 40, len(problems)

    return clean + problems
