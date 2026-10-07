"""End-to-end multi-turn booking/cancel/intake flows (SPEC 7 nodes 5, 7, 8).
Needs a running FHIR server with seeded patients and a running Postgres
(for the LangGraph checkpointer) -- creates its own throwaway patient/slots
rather than depending on `make seed` having been run.
"""

import time
import uuid

import httpx
import pytest
from specmcp import SpecMCPServer

from assistant.checkpointer import build_checkpointer
from assistant.graph import build_graph

PATIENT_ID = "test-patient-booking-flow"


def _search(fhir_base_url: str, path: str, params: dict) -> dict:
    """HAPI's search index can lag the primary DB by a moment right after a
    write (observed directly: a search immediately following a successful
    POST/PUT/status-change sometimes returns stale results either way --
    missing a just-created resource, or still showing a just-cancelled one).
    A short fixed pause beats asserting on a known race condition.

    `_total=accurate` and a generous `_count` are defaults, not optional:
    this module reuses one fixed patient id across every run this repo has
    ever done against this HAPI instance (no teardown between sessions), so
    its appointment count keeps growing. Confirmed directly that once it
    passed a few dozen, HAPI stopped including `total` in the response at
    all (a `KeyError`, not a stale-data issue) and paginated at 20 entries
    by default -- both silently wrong for a test that needs an exact count.
    """
    time.sleep(1.5)
    full_params = {"_count": 100, "_total": "accurate", **params}
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{fhir_base_url}/{path}", params=full_params)
    resp.raise_for_status()
    return resp.json()


def _count_booked_appointments(fhir_base_url: str, patient_id: str) -> int:
    """Not `_search(..., {"status": "booked"})`: confirmed directly against a
    live HAPI server that its `status` token search index can stay stale for
    10+ seconds (and several more writes) after a status change actually
    commits -- the same staleness assistant/cancel.py's extract_appointment_options
    now works around. Fetches by patient only and counts fresh resource
    bodies client-side instead, which was verified accurate even when the
    `status=booked` search parameter wasn't.
    """
    bundle = _search(fhir_base_url, "Appointment", {"patient": f"Patient/{patient_id}"})
    return sum(1 for e in bundle.get("entry", []) if e.get("resource", {}).get("status") == "booked")


@pytest.fixture(scope="module", autouse=True)
def _drain_pre_existing_booked_appointments(fhir_base_url):
    """This module reuses one fixed patient id (PATIENT_ID) across every run
    this repo has ever done against this HAPI instance -- no teardown
    between sessions, and earlier debugging sessions genuinely left some
    appointments stuck in `status: booked` (caught directly: the fixed
    30-iteration cancel loop in test_full_cancel_conversation_updates_the_appointment
    couldn't drain an unbounded historical backlog). Rather than raise that
    bound arbitrarily, start every run of this module from a clean slate by
    cancelling anything already booked before any test runs, so each test's
    own assertions are about what *it* did, not about history.
    """
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{fhir_base_url}/Appointment", params={"patient": f"Patient/{PATIENT_ID}", "_count": 200})
        resp.raise_for_status()
        for entry in resp.json().get("entry", []):
            resource = entry["resource"]
            if resource.get("status") == "booked":
                client.put(f"{fhir_base_url}/Appointment/{resource['id']}", json={**resource, "status": "cancelled"})


@pytest.fixture(scope="module")
def patient_id(fhir_base_url):
    patient = {
        "resourceType": "Patient",
        "id": PATIENT_ID,
        "name": [{"use": "official", "given": ["Booking"], "family": "FlowTestSubject"}],
        "gender": "male",
    }
    schedule = {"resourceType": "Schedule", "id": "test-sched-booking-flow", "active": True}
    slot = {
        "resourceType": "Slot",
        "id": "test-slot-booking-flow-1",
        "schedule": {"reference": "Schedule/test-sched-booking-flow"},
        "status": "free",
        "start": "2099-01-01T09:00:00+00:00",
        "end": "2099-01-01T10:00:00+00:00",
    }
    with httpx.Client(timeout=10.0) as client:
        for resource in (patient, schedule, slot):
            resp = client.put(f"{fhir_base_url}/{resource['resourceType']}/{resource['id']}", json=resource)
            resp.raise_for_status()
    return PATIENT_ID


@pytest.fixture(scope="module")
def graph(fhir_base_url):
    specmcp_server = SpecMCPServer(fhir_base_url)
    checkpointer = build_checkpointer()
    return build_graph(specmcp_server, checkpointer=checkpointer)


def _thread_config():
    return {"configurable": {"thread_id": f"test-{uuid.uuid4()}"}}


def test_full_booking_conversation_creates_a_real_appointment(graph, patient_id, fhir_base_url):
    config = _thread_config()

    t1 = graph.invoke({"patient_id": patient_id, "actor": "test", "message": "I want to book an appointment", "trace": []}, config=config)
    assert t1["booking_stage"] == "slots_offered"
    assert "1." in t1["reply"]

    t2 = graph.invoke({"patient_id": patient_id, "actor": "test", "message": "1", "trace": []}, config=config)
    assert t2["booking_stage"] == "awaiting_confirmation"
    assert "confirm" in t2["reply"].lower()

    t3 = graph.invoke({"patient_id": patient_id, "actor": "test", "message": "yes", "trace": []}, config=config)
    assert t3["booking_stage"] == "confirmed"

    assert _count_booked_appointments(fhir_base_url, patient_id) >= 1


def test_declining_the_booking_does_not_create_an_appointment(graph, patient_id, fhir_base_url):
    config = _thread_config()
    graph.invoke({"patient_id": patient_id, "actor": "test", "message": "book an appointment", "trace": []}, config=config)
    t2 = graph.invoke({"patient_id": patient_id, "actor": "test", "message": "1", "trace": []}, config=config)
    assert t2["booking_stage"] == "awaiting_confirmation"

    before = _search(fhir_base_url, "Appointment", {"patient": f"Patient/{patient_id}"})["total"]

    t3 = graph.invoke({"patient_id": patient_id, "actor": "test", "message": "no", "trace": []}, config=config)
    assert t3["booking_stage"] is None

    after = _search(fhir_base_url, "Appointment", {"patient": f"Patient/{patient_id}"})["total"]
    assert after == before


def test_red_flag_mid_booking_escalates_instead_of_continuing(graph, patient_id):
    config = _thread_config()
    graph.invoke({"patient_id": patient_id, "actor": "test", "message": "book an appointment", "trace": []}, config=config)
    result = graph.invoke(
        {"patient_id": patient_id, "actor": "test", "message": "actually I have severe chest pain right now", "trace": []},
        config=config,
    )
    assert result["escalated"] is True
    assert result["trace"] == ["language_detect", "safety_gate", "escalate"]
    assert "router" not in result["trace"]
    assert "booking_flow" not in result["trace"]


def test_full_cancel_conversation_updates_the_appointment(graph, patient_id, fhir_base_url):
    # Books its own appointment to cancel, but doesn't assume it's the only
    # booked one for this shared-fixture patient (other tests in this module
    # book against the same single test slot, since this module doesn't
    # model slots flipping to "busy" after booking -- see assistant/booking.py's
    # scope note) -- so this cancels in a loop until none remain, rather than
    # asserting a single cancel zeroes out the total.
    config = _thread_config()
    graph.invoke({"patient_id": patient_id, "actor": "test", "message": "book an appointment", "trace": []}, config=config)
    graph.invoke({"patient_id": patient_id, "actor": "test", "message": "1", "trace": []}, config=config)
    graph.invoke({"patient_id": patient_id, "actor": "test", "message": "yes", "trace": []}, config=config)

    for _ in range(30):  # generous upper bound; breaks as soon as none remain
        cancel_config = _thread_config()
        c1 = graph.invoke({"patient_id": patient_id, "actor": "test", "message": "cancel my appointment", "trace": []}, config=cancel_config)
        if c1["cancel_stage"] is None:  # no_appointments_message path
            break
        assert c1["cancel_stage"] == "choosing"

        c2 = graph.invoke({"patient_id": patient_id, "actor": "test", "message": "1", "trace": []}, config=cancel_config)
        assert c2["cancel_stage"] == "awaiting_confirmation"

        c3 = graph.invoke({"patient_id": patient_id, "actor": "test", "message": "yes", "trace": []}, config=cancel_config)
        assert c3["cancel_stage"] == "cancelled"

    assert _count_booked_appointments(fhir_base_url, patient_id) == 0


def test_full_intake_conversation_writes_questionnaire_response(graph, patient_id, fhir_base_url):
    config = _thread_config()
    replies = []
    for message in [
        "I need to do my pre-visit intake",
        "My knee hurts",
        "About 3 days",
        "7 out of 10",
        "No known allergies",
    ]:
        result = graph.invoke({"patient_id": patient_id, "actor": "test", "message": message, "trace": []}, config=config)
        replies.append(result["reply"])

    assert result["intake_complete"] is True
    assert result["intake_answers"]["chief_complaint"] == "My knee hurts"

    bundle = _search(fhir_base_url, "QuestionnaireResponse", {"subject": f"Patient/{patient_id}"})
    assert bundle["total"] >= 1
    latest = bundle["entry"][-1]["resource"]
    answers = {item["linkId"]: item["answer"][0]["valueString"] for item in latest["item"]}
    assert answers["chief_complaint"] == "My knee hurts"
    assert answers["allergies"] == "No known allergies"
