"""POST /v1/chat (SPEC 9): patient conversation turn, SSE response."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.api.dependencies import get_graph
from assistant.transcript import log_turn

router = APIRouter()
logger = logging.getLogger(__name__)


def _log_turn_best_effort(thread_id: str, patient_id: str, role: str, text: str, language: str | None) -> None:
    """Transcript logging (for QA/audit) masks PII via a spaCy-backed model
    that's genuinely memory-hungry to load on first use -- on a
    memory-constrained host this can raise MemoryError. That's a side
    effect failing, not the conversation itself: the patient still gets
    their answer either way, so this never lets a logging failure turn into
    a failed chat turn. Logged loudly so the gap is visible operationally,
    not silently swallowed.
    """
    try:
        log_turn(thread_id, patient_id, role, text, language=language)
    except Exception:
        logger.exception("Failed to log conversation turn (thread_id=%s, role=%s) -- reply still sent", thread_id, role)


class ChatRequest(BaseModel):
    patient_id: str
    message: str
    thread_id: str | None = None


@router.post("/v1/chat")
def chat(body: ChatRequest, graph=Depends(get_graph)):
    thread_id = body.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke(
        {"patient_id": body.patient_id, "actor": thread_id, "message": body.message, "trace": []},
        config=config,
    )

    _log_turn_best_effort(thread_id, body.patient_id, "patient", body.message, result.get("language"))
    _log_turn_best_effort(thread_id, body.patient_id, "assistant", result["reply"], result.get("language"))

    event = {
        "thread_id": thread_id,
        "reply": result["reply"],
        "language": result.get("language"),
        "escalated": result.get("escalated", False),
        "intent": result.get("intent"),
        # Structured state so the patient app can render clickable slot/
        # appointment cards (SPEC 9: "appointment cards with confirm
        # buttons") instead of making the patient type a number back --
        # trimmed to just the fields a card needs, not the full internal
        # state (which also carries each option's complete FHIR resource,
        # kept server-side only).
        "booking_stage": result.get("booking_stage"),
        "offered_slots": [
            {"index": i, "start": s["start"], "end": s["end"], "practitioner_id": s["practitioner_id"]}
            for i, s in enumerate(result.get("offered_slots") or [])
        ],
        "cancel_stage": result.get("cancel_stage"),
        "cancellable_appointments": [
            {"index": i, "start": a["start"], "end": a["end"]}
            for i, a in enumerate(result.get("cancellable_appointments") or [])
        ],
        "intake_awaiting": result.get("intake_awaiting"),
    }

    def _stream():
        yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")
