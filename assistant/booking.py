"""Booking flow (SPEC 7 node 5): collects a time preference, searches slots,
confirms before booking. specmcp-backed (search_slots / book_appointment /
search_appointments / cancel_appointment) -- no LLM needed for the mechanics;
slot selection uses a numbered-list pattern ("reply with 1, 2 or 3") rather
than free-text slot parsing, which would need an LLM to do reliably.

Scope note: slots are only shown by start time, not by clinic/specialty --
resolving Schedule -> Practitioner -> PractitionerRole -> Organization for a
human-readable clinic/specialty label is a real FHIR chain this module
doesn't walk yet (it derives a practitioner id from the schedule reference's
naming convention, `Schedule/sched-{pract_id}`, which only works because
fhir/seed/clinic_resources.py happens to name them that way -- not a
general solution). A full implementation would resolve and display this.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from safety.text_normalize import normalize

AFFIRMATIVE_EN = ["yes", "yeah", "yep", "confirm", "sure", "ok", "okay", "please do", "sounds good"]
AFFIRMATIVE_AR = ["نعم", "تمام", "أكد", "أوافق", "حسنا", "موافق"]
NEGATIVE_EN = ["no", "nope", "cancel", "don't", "not now", "never mind"]
NEGATIVE_AR = ["لا", "الغاء", "ليس الآن"]

ORDINAL_WORDS_EN = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4}
ORDINAL_WORDS_AR = {"الأول": 0, "الاول": 0, "الثاني": 1, "الثالث": 2}


@dataclass(frozen=True)
class SlotOption:
    id: str
    start: str
    end: str
    practitioner_id: str
    # The full original Slot resource: FHIR PUT replaces the whole resource,
    # so marking it busy after booking (or free again after a cancellation)
    # has to send the complete original back with only `status` changed.
    resource: dict = field(default_factory=dict)


def extract_slot_options(search_result: dict) -> list[SlotOption]:
    options = []
    for entry in search_result.get("entry", []):
        resource = entry.get("resource", {})
        # Filtering on the resource body's own `status`, not relying solely on
        # the `status=free` search parameter, for the same reason documented
        # in assistant/cancel.py's extract_appointment_options: verified
        # directly that HAPI's `status` token search index can stay stale
        # well after a write commits. Here that would mean offering an
        # already-busy slot to a patient -- a real double-booking risk, not
        # just a cosmetic staleness issue.
        if resource.get("status") != "free":
            continue
        schedule_ref = resource.get("schedule", {}).get("reference", "")
        # "Schedule/sched-pract-00" -> "pract-00", per fhir/seed/clinic_resources.py's
        # naming convention (see module docstring -- not a general FHIR resolution).
        practitioner_id = re.sub(r"^Schedule/sched-", "", schedule_ref) or "unknown"
        options.append(
            SlotOption(
                id=resource["id"],
                start=resource["start"],
                end=resource["end"],
                practitioner_id=practitioner_id,
                resource=resource,
            )
        )
    return options


def format_time(iso_ts: str, language: str) -> str:
    dt = datetime.fromisoformat(iso_ts)
    if language == "ar":
        return dt.strftime("%Y-%m-%d %H:%M")
    return dt.strftime("%a %d %b, %H:%M")


def format_slot_options(options: list[SlotOption], language: str) -> str:
    if language == "ar":
        header = "وجدت هذه المواعيد المتاحة، يرجى الرد برقم الموعد الذي تريده:"
        lines = [f"{i + 1}. {format_time(o.start, language)} — {o.practitioner_id}" for i, o in enumerate(options)]
    else:
        header = "I found these available slots -- reply with the number of the one you'd like:"
        lines = [f"{i + 1}. {format_time(o.start, language)} with {o.practitioner_id}" for i, o in enumerate(options)]
    return "\n".join([header, *lines])


def parse_choice(message: str, n_options: int) -> int | None:
    """Returns a 0-based index, or None if the message doesn't clearly pick one."""
    norm = normalize(message)

    digit_match = re.search(r"\b([1-9])\b", norm)
    if digit_match:
        idx = int(digit_match.group(1)) - 1
        if 0 <= idx < n_options:
            return idx

    for word, idx in {**ORDINAL_WORDS_EN, **ORDINAL_WORDS_AR}.items():
        if normalize(word) in norm and idx < n_options:
            return idx

    return None


def is_affirmative(message: str) -> bool:
    norm = normalize(message)
    if any(normalize(w) in norm for w in NEGATIVE_EN + NEGATIVE_AR):
        return False
    return any(normalize(w) in norm for w in AFFIRMATIVE_EN + AFFIRMATIVE_AR)


def is_negative(message: str) -> bool:
    norm = normalize(message)
    return any(normalize(w) in norm for w in NEGATIVE_EN + NEGATIVE_AR)


def confirm_prompt(option: SlotOption, language: str) -> str:
    time_str = format_time(option.start, language)
    if language == "ar":
        return f"حسنا، موعد {time_str} مع {option.practitioner_id}. هل أؤكد الحجز؟ (نعم/لا)"
    return f"Great, {time_str} with {option.practitioner_id}. Shall I confirm this booking? (yes/no)"


def booking_confirmed_message(option: SlotOption, language: str) -> str:
    time_str = format_time(option.start, language)
    if language == "ar":
        return f"تم تأكيد موعدك في {time_str} مع {option.practitioner_id}. نتطلع لرؤيتك."
    return f"Your appointment is confirmed for {time_str} with {option.practitioner_id}. See you then."


def build_appointment_resource(patient_id: str, option: SlotOption) -> dict:
    return {
        "resourceType": "Appointment",
        "status": "booked",
        "slot": [{"reference": f"Slot/{option.id}"}],
        "start": option.start,
        "end": option.end,
        "participant": [{"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"}],
    }


def next_available_slots_params(count: int = 3) -> dict:
    now = datetime.now(UTC).isoformat()
    return {"status": "free", "start": f"ge{now}", "_count": count}


def build_busy_slot_resource(option: SlotOption) -> dict:
    """The full original Slot resource with only `status` changed -- see
    SlotOption's docstring for why a minimal reconstruction would be wrong."""
    return {**option.resource, "status": "busy"}


def build_free_slot_resource(slot_resource: dict) -> dict:
    return {**slot_resource, "status": "free"}
