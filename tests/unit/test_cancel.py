"""Cancel flow helpers -- pure logic, no FHIR needed."""

from assistant.cancel import (
    build_cancelled_appointment_resource,
    extract_appointment_options,
    search_appointments_params,
)

SAMPLE_SEARCH_RESULT = {
    "resourceType": "Bundle",
    "entry": [
        {
            "resource": {
                "resourceType": "Appointment",
                "id": "appt-2",
                "status": "booked",
                "start": "2026-10-05T09:00:00+00:00",
                "end": "2026-10-05T10:00:00+00:00",
                "participant": [{"actor": {"reference": "Patient/p1"}, "status": "accepted"}],
            }
        },
        {
            "resource": {
                "resourceType": "Appointment",
                "id": "appt-1",
                "status": "booked",
                "start": "2026-10-01T09:00:00+00:00",
                "end": "2026-10-01T10:00:00+00:00",
                "participant": [{"actor": {"reference": "Patient/p1"}, "status": "accepted"}],
            }
        },
    ],
}


def test_extract_appointment_options_sorted_by_start():
    options = extract_appointment_options(SAMPLE_SEARCH_RESULT)
    assert [o.id for o in options] == ["appt-1", "appt-2"]  # soonest first, not search order


def test_build_cancelled_appointment_resource_preserves_other_fields():
    options = extract_appointment_options(SAMPLE_SEARCH_RESULT)
    cancelled = build_cancelled_appointment_resource(options[0])
    assert cancelled["status"] == "cancelled"
    assert cancelled["participant"] == [{"actor": {"reference": "Patient/p1"}, "status": "accepted"}]
    assert cancelled["id"] == "appt-1"


def test_search_appointments_params():
    # No `status` filter: see extract_appointment_options's docstring --
    # HAPI's `status` search-parameter index can stay stale after a write, so
    # filtering is done client-side on each entry's fresh resource body
    # instead of trusting a `status=booked` search match. `_count: 100`
    # guards against the default 20-per-page pagination hiding older
    # appointments for a patient with many on record.
    params = search_appointments_params("patient-42")
    assert params == {"patient": "Patient/patient-42", "_count": 100}


def test_extract_appointment_options_excludes_non_booked_even_if_search_matched_them():
    # Regression test for the same staleness issue: a search can still
    # return an appointment that's already been cancelled.
    result = {
        "entry": [
            {
                "resource": {
                    "id": "appt-1", "status": "cancelled",
                    "start": "2026-10-01T09:00:00+00:00", "end": "2026-10-01T10:00:00+00:00",
                }
            },
            {
                "resource": {
                    "id": "appt-2", "status": "booked",
                    "start": "2026-10-05T09:00:00+00:00", "end": "2026-10-05T10:00:00+00:00",
                }
            },
        ]
    }
    options = extract_appointment_options(result)
    assert [o.id for o in options] == ["appt-2"]
