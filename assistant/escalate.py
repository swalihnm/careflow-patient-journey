"""Red-flag/crisis escalation (SPEC 7 node 9): emergency guidance + nurse
alert, every escalation logged. Deliberately has no LLM dependency anywhere
in this module -- this is the one path in the graph that must work even if
every optional component is unavailable. The patient-facing message and the
nurse alert never depend on masking succeeding, for exactly that reason;
only the *audit log's* reason field does (see _safe_masked_reason below).

UAE emergency numbers per SPEC section 7: ambulance 998, police 999 -- not
re-verified against a current official source (see safety/protocol.yaml's
same caveat).
"""

import logging

import trustcore

logger = logging.getLogger(__name__)

EMERGENCY_MESSAGE_EN = (
    "This sounds like it could be a medical emergency. Please call 998 for an "
    "ambulance or go to the nearest emergency room right away. I've alerted "
    "our nursing team. This assistant can't give medical advice -- please "
    "seek emergency care now."
)
EMERGENCY_MESSAGE_AR = (
    "يبدو أن هذه قد تكون حالة طوارئ طبية. يرجى الاتصال بالرقم 998 لطلب "
    "سيارة إسعاف أو التوجه إلى أقرب قسم طوارئ فورا. لقد قمت بتنبيه فريق "
    "التمريض. لا يمكن لهذا المساعد تقديم نصيحة طبية -- يرجى طلب الرعاية "
    "الطارئة الآن."
)

CRISIS_MESSAGE_EN = (
    "I'm really concerned about what you've shared. You don't have to go "
    "through this alone. Please reach out right now: call 998 for emergency "
    "help, or a crisis line if one is available to you. I've also alerted "
    "our team so a person can follow up with you directly."
)
CRISIS_MESSAGE_AR = (
    "أنا قلق جدا بشأن ما شاركته. لست مضطرا لمواجهة هذا وحدك. يرجى التواصل "
    "الآن: اتصل بالرقم 998 للمساعدة الطارئة، أو بخط أزمات إن كان متاحا لديك. "
    "كما قمت بتنبيه فريقنا حتى يتابع معك أحد الأشخاص مباشرة."
)


def build_escalation_message(escalation_type: str, language: str) -> str:
    if escalation_type == "crisis":
        return CRISIS_MESSAGE_AR if language == "ar" else CRISIS_MESSAGE_EN
    return EMERGENCY_MESSAGE_AR if language == "ar" else EMERGENCY_MESSAGE_EN


def build_nurse_alert(patient_id: str, category: str, escalation_type: str, matched_text: str) -> dict:
    """FHIR Communication resource alerting the nursing team."""
    return {
        "resourceType": "Communication",
        "id": f"escalation-{patient_id}-{category}",
        "status": "in-progress",
        "priority": "stat",
        "category": [{"text": "red-flag-escalation"}],
        "subject": {"reference": f"Patient/{patient_id}"},
        "payload": [{"contentString": f"Red-flag escalation ({escalation_type}): category={category}"}],
        "note": [{"text": f"Trigger phrase matched: {matched_text}"}],
    }


def _safe_masked_reason(escalation_type: str, category: str, matched_text: str) -> str:
    """Real bug found and fixed: the audit log's `reason` field used to be
    built from the patient's raw, unmasked message (`f"... matched
    {matched_text!r}"`) -- confirmed directly that a message like "This is
    Fatima Al Nahyan, phone 0501234567, I have severe chest pain" writes
    that name and phone number verbatim into ops.audit_log, which the
    auditor-role /v1/audit view doesn't mask (it only masks actor/
    resource_id, not reason -- SPEC's own acceptance criterion for this is
    "no unmasked PHI-like values in logs, automated scan in CI").

    Masking is wrapped here, not imported at module load time or left
    unguarded, because safety/masking.py's Presidio+spaCy analyzer is
    genuinely memory-hungry (a real, previously-hit MemoryError under this
    project's host constraints -- see PROGRESS.md) and this module's whole
    design principle is that escalation must still work if every optional
    component is unavailable. If masking itself fails, the fallback omits
    the matched text entirely rather than falling back to the unmasked
    original, which would silently defeat the fix on exactly the failure
    path most likely to matter.
    """
    try:
        from safety.masking import mask_text

        masked = mask_text(matched_text).masked_text
    except Exception:
        logger.exception("Masking failed while building escalation audit reason -- omitting matched text")
        return f"{escalation_type}:{category} (matched text omitted: masking unavailable)"
    return f"{escalation_type}:{category} matched {masked!r}"


def escalate(
    patient_id: str,
    category: str,
    escalation_type: str,
    matched_text: str,
    language: str,
    actor: str,
) -> dict:
    """Builds the patient-facing message and the FHIR Communication to alert
    the nursing team, and logs the escalation. Does not itself POST to FHIR
    -- the graph node does that through specmcp's write_communication tool,
    so the write is policy-checked and audited the same way every other
    assistant-initiated write is.
    """
    message = build_escalation_message(escalation_type, language)

    trustcore.record(
        actor=actor,
        actor_role="assistant",
        action="escalation",
        resource_type="Communication",
        resource_id=patient_id,
        result="allow",
        reason=_safe_masked_reason(escalation_type, category, matched_text),
    )

    return {
        "message": message,
        "nurse_alert": build_nurse_alert(patient_id, category, escalation_type, matched_text),
    }
