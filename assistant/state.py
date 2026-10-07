"""Conversation state shared across every graph node (SPEC 7).

Persisted across turns by the graph's checkpointer (assistant/graph.py), so
every field here must be JSON-serializable (plain dicts/lists/strings, not
dataclass instances) -- multi-turn flows (booking/cancel/intake) carry their
progress in this state between separate `.invoke()` calls on the same thread.
"""

from typing import Any, NotRequired, TypedDict


class ConversationState(TypedDict):
    patient_id: str
    actor: str  # session id, for audit
    message: str
    language: NotRequired[str]
    is_mixed_language: NotRequired[bool]
    red_flag_category: NotRequired[str | None]
    red_flag_escalation: NotRequired[str | None]
    scope_violation_category: NotRequired[str | None]
    intent: NotRequired[str]
    reply: NotRequired[str]
    escalated: NotRequired[bool]

    # Booking flow (assistant/booking.py). booking_stage: None | "slots_offered"
    # | "awaiting_confirmation" | "confirmed".
    booking_stage: NotRequired[str | None]
    offered_slots: NotRequired[list[dict[str, Any]]]
    selected_slot: NotRequired[dict[str, Any] | None]

    # Cancel (and reschedule, see graph.py) flow (assistant/cancel.py).
    # cancel_stage: None | "choosing" | "awaiting_confirmation" | "cancelled".
    cancel_stage: NotRequired[str | None]
    cancellable_appointments: NotRequired[list[dict[str, Any]]]
    selected_appointment: NotRequired[dict[str, Any] | None]
    offer_rebook_after_cancel: NotRequired[bool]

    # Intake flow (assistant/intake.py). intake_awaiting holds the question
    # id the last turn's reply answers; None means either not started or complete.
    intake_answers: NotRequired[dict[str, str]]
    intake_awaiting: NotRequired[str | None]
    intake_complete: NotRequired[bool]

    # Node names visited THIS TURN, in order -- SPEC 7 acceptance criteria:
    # "Safety gate runs before routing on 100% of turns (visible in traces)."
    # Reset at the start of every turn by language_detect_node, not
    # accumulated across the whole conversation.
    trace: list[str]


def append_trace(state: ConversationState, node: str) -> list[str]:
    return [*state.get("trace", []), node]


def in_progress_flow(state: ConversationState) -> str | None:
    """Which multi-turn flow (if any) is mid-conversation and should receive
    this turn's message directly, bypassing intent classification -- e.g. a
    reply of "2" to "which slot?" must not be re-routed by the intent
    classifier, which would classify "2" as unclear."""
    if state.get("booking_stage") not in (None, "confirmed"):
        return "booking_flow"
    if state.get("cancel_stage") not in (None, "cancelled"):
        return "cancel_flow"
    if state.get("intake_awaiting") is not None:
        return "intake_flow"
    return None
