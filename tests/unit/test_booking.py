"""Booking flow helpers (SPEC 7 node 5) -- pure logic, no FHIR needed."""

from assistant.booking import (
    SlotOption,
    build_appointment_resource,
    extract_slot_options,
    is_affirmative,
    is_negative,
    parse_choice,
)

SAMPLE_SEARCH_RESULT = {
    "resourceType": "Bundle",
    "entry": [
        {
            "resource": {
                "resourceType": "Slot",
                "id": "slot-pract-00-2026100109",
                "schedule": {"reference": "Schedule/sched-pract-00"},
                "status": "free",
                "start": "2026-10-01T09:00:00+00:00",
                "end": "2026-10-01T10:00:00+00:00",
            }
        },
        {
            "resource": {
                "resourceType": "Slot",
                "id": "slot-pract-01-2026100110",
                "schedule": {"reference": "Schedule/sched-pract-01"},
                "status": "free",
                "start": "2026-10-01T10:00:00+00:00",
                "end": "2026-10-01T11:00:00+00:00",
            }
        },
    ],
}


def test_extract_slot_options():
    options = extract_slot_options(SAMPLE_SEARCH_RESULT)
    assert len(options) == 2
    assert options[0].id == "slot-pract-00-2026100109"
    assert options[0].practitioner_id == "pract-00"


def test_extract_slot_options_excludes_busy_slots_even_if_search_matched_them():
    # Regression test: HAPI's `status` search-parameter index can stay stale
    # after a write, so a `status=free` search can still return an already
    # -busy slot. extract_slot_options must not trust the search match alone
    # -- it has to check each slot's own fresh `status` field, or a patient
    # could be offered (and book) an already-taken slot.
    result = {
        "entry": [
            {
                "resource": {
                    "id": "slot-1", "schedule": {"reference": "Schedule/sched-pract-00"},
                    "status": "busy", "start": "2026-10-01T09:00:00+00:00", "end": "2026-10-01T10:00:00+00:00",
                }
            },
            {
                "resource": {
                    "id": "slot-2", "schedule": {"reference": "Schedule/sched-pract-00"},
                    "status": "free", "start": "2026-10-01T10:00:00+00:00", "end": "2026-10-01T11:00:00+00:00",
                }
            },
        ]
    }
    options = extract_slot_options(result)
    assert [o.id for o in options] == ["slot-2"]


def test_parse_choice_by_digit():
    assert parse_choice("2", 3) == 1
    assert parse_choice("I'll take option 1", 3) == 0
    assert parse_choice("رقم 3 من فضلك", 3) == 2


def test_parse_choice_by_ordinal_word():
    assert parse_choice("the second one please", 3) == 1
    assert parse_choice("الأول", 3) == 0


def test_parse_choice_out_of_range_returns_none():
    assert parse_choice("5", 3) is None


def test_parse_choice_no_match_returns_none():
    assert parse_choice("what time works best", 3) is None


def test_is_affirmative():
    assert is_affirmative("yes please") is True
    assert is_affirmative("نعم") is True
    assert is_affirmative("no thanks") is False
    assert is_affirmative("what time is it") is False


def test_is_negative():
    assert is_negative("no, cancel that") is True
    assert is_negative("يجب أن أفكر") is False  # "I need to think" -- not a clear negative


def test_build_appointment_resource():
    option = SlotOption(id="slot-1", start="2026-10-01T09:00:00+00:00", end="2026-10-01T10:00:00+00:00", practitioner_id="pract-00")
    resource = build_appointment_resource("patient-42", option)
    assert resource["resourceType"] == "Appointment"
    assert resource["status"] == "booked"
    assert resource["slot"][0]["reference"] == "Slot/slot-1"
    assert resource["participant"][0]["actor"]["reference"] == "Patient/patient-42"
