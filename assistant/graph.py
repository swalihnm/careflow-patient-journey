"""LangGraph conversation graph (SPEC 7).

The safety gate runs before the router on every turn, unconditionally --
SPEC 7 acceptance criteria: "Safety gate runs before routing on 100% of
turns (visible in traces)." That ordering is a real graph edge here
(language_detect -> safety_gate -> scope_guard -> router-or-continue), not a
convention individual nodes are expected to honor, so no future change to
routing logic can accidentally bypass it.

Multi-turn flows (booking, cancel, intake) persist their progress in
ConversationState via the graph's checkpointer (build_graph()'s optional
`checkpointer` argument -- assistant/checkpointer.py builds a Postgres-backed
one; omit it, or pass None, for a single-invoke test with no persistence),
keyed by a `thread_id` in the invoke config. Once a flow is in progress,
`in_progress_flow()` routes straight to it -- bypassing intent
classification -- so a reply like "2" to "which slot?" isn't re-classified
as an unrelated intent.

Scope simplification: "reschedule" is handled as cancel-then-rebook (the
cancel flow ends by inviting the patient to book a new time), not as a
single combined flow with its own state machine -- see assistant/cancel.py.
"""

import dataclasses
import time

import httpx
from langgraph.graph import END, StateGraph
from specmcp import PolicyDenied

from assistant.booking import (
    booking_confirmed_message as slot_confirmed_message,
)
from assistant.booking import (
    build_appointment_resource,
    build_busy_slot_resource,
    build_free_slot_resource,
    confirm_prompt,
    extract_slot_options,
    format_slot_options,
    is_affirmative,
    is_negative,
    next_available_slots_params,
)
from assistant.booking import (
    parse_choice as parse_slot_choice,
)
from assistant.cancel import (
    build_cancelled_appointment_resource,
    cancel_confirm_prompt,
    cancel_confirmed_message,
    extract_appointment_options,
    format_appointment_options,
    no_appointments_message,
    search_appointments_params,
)
from assistant.coverage import answer_coverage_question
from assistant.escalate import escalate
from assistant.intake import IntakeState, build_clinician_summary, build_questionnaire_response
from assistant.language import detect_language
from assistant.router import classify_intent
from assistant.state import ConversationState, append_trace, in_progress_flow
from safety.red_flag import check_red_flag
from safety.scope_guard import check_scope

SCOPE_REFUSAL_EN = (
    "I'm not able to help with that -- I can't give a diagnosis, medication advice, or interpret "
    "test results. I can help you book an appointment or connect you with a clinician who can."
)
SCOPE_REFUSAL_AR = (
    "لا يمكنني المساعدة في ذلك -- لا يمكنني تقديم تشخيص أو نصيحة دوائية أو تفسير نتائج الفحوصات. "
    "يمكنني مساعدتك في حجز موعد أو توصيلك بطبيب يمكنه ذلك."
)

CLINIC_INFO_EN = (
    "Downtown Dubai and Marina clinics are open Sunday-Thursday 8:00-20:00 and Friday-Saturday "
    "9:00-17:00. You can ask me about booking, coverage, or say 'talk to a person' any time."
)
CLINIC_INFO_AR = (
    "عيادتا وسط دبي ومارينا مفتوحتان من الأحد إلى الخميس 8:00-20:00 ومن الجمعة إلى السبت "
    "9:00-17:00. يمكنك سؤالي عن الحجز أو التغطية، أو قول 'أريد التحدث مع شخص' في أي وقت."
)

HANDOVER_EN = "Of course -- connecting you with a member of our team now."
HANDOVER_AR = "بالتأكيد -- سأقوم بتوصيلك بأحد أفراد فريقنا الآن."

UNCLEAR_EN = (
    "I can help you book an appointment, answer coverage questions, or start your pre-visit "
    "intake. What would you like to do?"
)
UNCLEAR_AR = (
    "يمكنني مساعدتك في حجز موعد، أو الإجابة عن أسئلة التغطية، أو بدء تسجيل بيانات ما قبل "
    "الزيارة. ماذا تود أن تفعل؟"
)

BOOKING_NO_SLOTS_EN = "I couldn't find any available slots right now -- let me connect you with our booking team."
BOOKING_NO_SLOTS_AR = "لم أجد أي مواعيد متاحة حاليا -- سأقوم بتوصيلك بفريق الحجز لدينا."
BOOKING_UNRECOGNISED_CHOICE_EN = "Sorry, I didn't catch that -- please reply with the number of the slot you'd like."
BOOKING_UNRECOGNISED_CHOICE_AR = "عذرا، لم أفهم ذلك -- يرجى الرد برقم الموعد الذي تريده."
BOOKING_DECLINED_EN = "No problem -- let me know if you'd like to see other times."
BOOKING_DECLINED_AR = "لا مشكلة -- أخبرني إذا أردت رؤية أوقات أخرى."
CANCEL_UNRECOGNISED_CHOICE_EN = "Sorry, I didn't catch that -- please reply with the number of the appointment."
CANCEL_UNRECOGNISED_CHOICE_AR = "عذرا، لم أفهم ذلك -- يرجى الرد برقم الموعد."
CANCEL_DECLINED_EN = "No problem -- your appointment is unchanged."
CANCEL_DECLINED_AR = "لا مشكلة -- موعدك لم يتغير."


def language_detect_node(state: ConversationState) -> dict:
    result = detect_language(state["message"])
    return {
        "language": result.language,
        "is_mixed_language": result.is_mixed,
        "trace": ["language_detect"],  # reset per turn -- see state.py's ConversationState docstring
    }


def safety_gate_node(state: ConversationState) -> dict:
    match = check_red_flag(state["message"])
    return {
        "red_flag_category": match.category if match.is_red_flag else None,
        "red_flag_escalation": match.escalation if match.is_red_flag else None,
        "trace": append_trace(state, "safety_gate"),
    }


def scope_guard_node(state: ConversationState) -> dict:
    violation = check_scope(state["message"])
    return {
        "scope_violation_category": violation.category if violation.is_violation else None,
        "trace": append_trace(state, "scope_guard"),
    }


def router_node(state: ConversationState) -> dict:
    return {"intent": classify_intent(state["message"]), "trace": append_trace(state, "router")}


def escalate_node(state: ConversationState) -> dict:
    result = escalate(
        patient_id=state["patient_id"],
        category=state.get("red_flag_category") or "unknown",
        escalation_type=state.get("red_flag_escalation") or "emergency",
        matched_text=state["message"],
        language=state.get("language", "en"),
        actor=state["actor"],
    )
    return {"reply": result["message"], "escalated": True, "trace": append_trace(state, "escalate")}


def scope_refusal_node(state: ConversationState) -> dict:
    text = SCOPE_REFUSAL_AR if state.get("language") == "ar" else SCOPE_REFUSAL_EN
    return {"reply": text, "trace": append_trace(state, "scope_refusal")}


def coverage_rag_node(state: ConversationState) -> dict:
    answer = answer_coverage_question(state["message"], state.get("language", "en"))
    return {"reply": answer.text, "trace": append_trace(state, "coverage_rag")}


def clinic_info_node(state: ConversationState) -> dict:
    text = CLINIC_INFO_AR if state.get("language") == "ar" else CLINIC_INFO_EN
    return {"reply": text, "trace": append_trace(state, "clinic_info")}


def handover_node(state: ConversationState) -> dict:
    text = HANDOVER_AR if state.get("language") == "ar" else HANDOVER_EN
    return {"reply": text, "trace": append_trace(state, "handover")}


def unclear_node(state: ConversationState) -> dict:
    text = UNCLEAR_AR if state.get("language") == "ar" else UNCLEAR_EN
    return {"reply": text, "trace": append_trace(state, "unclear")}


def make_booking_flow_node(specmcp_server):
    def booking_flow_node(state: ConversationState) -> dict:
        language = state.get("language", "en")
        stage = state.get("booking_stage")
        trace = append_trace(state, "booking_flow")

        if stage is None:
            result = specmcp_server.call(
                "search_slots", next_available_slots_params(), actor=state["actor"], role="assistant"
            )
            options = extract_slot_options(result)
            if not options:
                no_slots = BOOKING_NO_SLOTS_AR if language == "ar" else BOOKING_NO_SLOTS_EN
                return {"booking_stage": None, "reply": no_slots, "trace": trace}
            return {
                "booking_stage": "slots_offered",
                "offered_slots": [dataclasses.asdict(o) for o in options],
                "reply": format_slot_options(options, language),
                "trace": trace,
            }

        if stage == "slots_offered":
            offered = state.get("offered_slots", [])
            idx = parse_slot_choice(state["message"], len(offered))
            if idx is None:
                unrecognised = BOOKING_UNRECOGNISED_CHOICE_AR if language == "ar" else BOOKING_UNRECOGNISED_CHOICE_EN
                return {"reply": unrecognised, "trace": trace}
            selected = offered[idx]
            return {
                "booking_stage": "awaiting_confirmation",
                "selected_slot": selected,
                "reply": confirm_prompt(_slot_option(selected), language),
                "trace": trace,
            }

        if stage == "awaiting_confirmation":
            selected = state.get("selected_slot")
            if is_affirmative(state["message"]):
                option = _slot_option(selected)
                appointment = build_appointment_resource(state["patient_id"], option)
                specmcp_server.call(
                    "book_appointment", {"resource": appointment}, actor=state["actor"], role="assistant"
                )
                # Mark the slot busy so it isn't offered to the next patient.
                specmcp_server.call(
                    "update_slot",
                    {"id": option.id, "resource": build_busy_slot_resource(option)},
                    actor=state["actor"],
                    role="assistant",
                )
                return {
                    "booking_stage": "confirmed",
                    "reply": slot_confirmed_message(option, language),
                    "trace": trace,
                }
            if is_negative(state["message"]):
                declined = BOOKING_DECLINED_AR if language == "ar" else BOOKING_DECLINED_EN
                return {"booking_stage": None, "offered_slots": [], "selected_slot": None, "reply": declined, "trace": trace}
            return {"reply": confirm_prompt(_slot_option(selected), language), "trace": trace}

        # stage == "confirmed" (shouldn't normally re-enter; treat as a fresh request)
        return {"booking_stage": None, "trace": trace}

    return booking_flow_node


def _slot_option(d: dict):
    from assistant.booking import SlotOption

    return SlotOption(**d)


def make_cancel_flow_node(specmcp_server):
    def cancel_flow_node(state: ConversationState) -> dict:
        language = state.get("language", "en")
        stage = state.get("cancel_stage")
        offer_rebook = state.get("offer_rebook_after_cancel", False)
        trace = append_trace(state, "cancel_flow")

        if stage is None:
            options = _search_cancellable_appointments(specmcp_server, state["patient_id"], state["actor"])
            if not options:
                return {"cancel_stage": None, "reply": no_appointments_message(language), "trace": trace}
            return {
                "cancel_stage": "choosing",
                "cancellable_appointments": [dataclasses.asdict(o) for o in options],
                "reply": format_appointment_options(options, language),
                "trace": trace,
            }

        if stage == "choosing":
            options_raw = state.get("cancellable_appointments", [])
            idx = parse_slot_choice(state["message"], len(options_raw))
            if idx is None:
                unrecognised = CANCEL_UNRECOGNISED_CHOICE_AR if language == "ar" else CANCEL_UNRECOGNISED_CHOICE_EN
                return {"reply": unrecognised, "trace": trace}
            selected = options_raw[idx]
            return {
                "cancel_stage": "awaiting_confirmation",
                "selected_appointment": selected,
                "reply": cancel_confirm_prompt(_appointment_option(selected), language),
                "trace": trace,
            }

        if stage == "awaiting_confirmation":
            selected = state.get("selected_appointment")
            option = _appointment_option(selected)
            if is_affirmative(state["message"]):
                updated = build_cancelled_appointment_resource(option)
                specmcp_server.call(
                    "cancel_appointment", {"id": option.id, "resource": updated}, actor=state["actor"], role="assistant"
                )
                _free_up_slot(specmcp_server, option, state["actor"])
                return {
                    "cancel_stage": "cancelled",
                    "reply": cancel_confirmed_message(option, language, offer_rebook),
                    "trace": trace,
                }
            if is_negative(state["message"]):
                declined = CANCEL_DECLINED_AR if language == "ar" else CANCEL_DECLINED_EN
                return {
                    "cancel_stage": None,
                    "cancellable_appointments": [],
                    "selected_appointment": None,
                    "reply": declined,
                    "trace": trace,
                }
            return {"reply": cancel_confirm_prompt(option, language), "trace": trace}

        return {"cancel_stage": None, "trace": trace}

    return cancel_flow_node


def _search_cancellable_appointments(specmcp_server, patient_id: str, actor: str) -> list:
    """A search for a patient's appointments, called with no delay right
    after that same patient's own booking write, can miss the just-created
    resource *entirely* -- not just show it with a stale `status` (that's
    extract_appointment_options's job to work around; this is a different
    failure mode). Measured directly, more than once, on this host: a write
    can take 10+ seconds (one measurement: 13.4s) before a `patient`-filtered
    search sees it at all -- this is HAPI's real indexing throughput under
    this machine's current load (several unrelated Docker-based projects
    competing for RAM; see PROGRESS.md), not a fixed, small "replication
    lag." A short single retry (tried first) wasn't enough; this polls for
    up to ~20s, which only costs real latency in the specific case of a
    cancel request immediately following that same patient's own booking --
    the common case (nothing just booked, or the index already caught up)
    returns on the first attempt."""
    deadline = time.monotonic() + 20.0
    while True:
        result = specmcp_server.call(
            "search_appointments", search_appointments_params(patient_id), actor=actor, role="assistant"
        )
        options = extract_appointment_options(result)
        if options or time.monotonic() >= deadline:
            return options
        time.sleep(2.0)


def _appointment_option(d: dict):
    from assistant.cancel import AppointmentOption

    return AppointmentOption(**d)


def _free_up_slot(specmcp_server, appointment_option, actor: str) -> None:
    """Best-effort: not every Appointment references a Slot (e.g. one
    created outside this graph), so a missing/unresolvable reference is
    logged via the normal audit trail (as a policy denial or FHIR error from
    the tool calls themselves) rather than raised -- freeing the slot is a
    nice-to-have for realism, not something that should fail the cancellation
    the patient actually asked for."""
    slot_refs = appointment_option.resource.get("slot", [])
    if not slot_refs:
        return
    reference = slot_refs[0].get("reference", "")
    if not reference.startswith("Slot/"):
        return
    slot_id = reference.removeprefix("Slot/")

    try:
        slot_resource = specmcp_server.call("read_slot", {"id": slot_id}, actor=actor, role="assistant")
        specmcp_server.call(
            "update_slot",
            {"id": slot_id, "resource": build_free_slot_resource(slot_resource)},
            actor=actor,
            role="assistant",
        )
    except (PolicyDenied, httpx.HTTPStatusError):
        pass


def make_intake_flow_node(specmcp_server):
    def intake_flow_node(state: ConversationState) -> dict:
        language = state.get("language", "en")
        trace = append_trace(state, "intake_flow")

        answers = dict(state.get("intake_answers", {}))
        awaiting = state.get("intake_awaiting")
        if awaiting:
            answers[awaiting] = state["message"]

        istate = IntakeState(answers=answers)
        next_q = istate.next_question

        if next_q is not None:
            question_text = next_q["text_ar"] if language == "ar" else next_q["text_en"]
            return {
                "intake_answers": answers,
                "intake_awaiting": next_q["id"],
                "reply": question_text,
                "trace": trace,
            }

        qr = build_questionnaire_response(state["patient_id"], istate)
        specmcp_server.call("write_questionnaire_response", {"resource": qr}, actor=state["actor"], role="assistant")
        build_clinician_summary(istate)  # written to the QuestionnaireResponse's own record via FHIR, not repeated here

        done_en = "Thanks, that's everything I need. Your care team will see this before your visit."
        done_ar = "شكرا، هذا كل ما أحتاجه. سيطلع فريق الرعاية على هذا قبل زيارتك."
        return {
            "intake_answers": answers,
            "intake_awaiting": None,
            "intake_complete": True,
            "reply": done_ar if language == "ar" else done_en,
            "trace": trace,
        }

    return intake_flow_node


def route_after_safety(state: ConversationState) -> str:
    return "escalate" if state.get("red_flag_category") else "scope_guard"


def route_after_scope(state: ConversationState) -> str:
    if state.get("scope_violation_category"):
        return "scope_refusal"
    return in_progress_flow(state) or "router"


_INTENT_TO_NODE = {
    "coverage_question": "coverage_rag",
    "clinic_info": "clinic_info",
    "handover": "handover",
    "book": "booking_flow",
    "reschedule": "cancel_flow_reschedule",
    "cancel": "cancel_flow",
    "intake": "intake_flow",
}


def route_after_router(state: ConversationState) -> str:
    return _INTENT_TO_NODE.get(state.get("intent", "unclear"), "unclear")


def build_graph(specmcp_server, checkpointer=None):
    graph = StateGraph(ConversationState)

    graph.add_node("language_detect", language_detect_node)
    graph.add_node("safety_gate", safety_gate_node)
    graph.add_node("scope_guard", scope_guard_node)
    graph.add_node("router", router_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("scope_refusal", scope_refusal_node)
    graph.add_node("coverage_rag", coverage_rag_node)
    graph.add_node("clinic_info", clinic_info_node)
    graph.add_node("handover", handover_node)
    graph.add_node("unclear", unclear_node)
    graph.add_node("booking_flow", make_booking_flow_node(specmcp_server))
    graph.add_node("cancel_flow", make_cancel_flow_node(specmcp_server))
    # Same node as "cancel_flow", registered under a second name so the
    # "reschedule" intent can set offer_rebook_after_cancel=True before
    # entering it (see the wrapper below) while "cancel" doesn't.
    graph.add_node("cancel_flow_reschedule", _reschedule_entry(make_cancel_flow_node(specmcp_server)))
    graph.add_node("intake_flow", make_intake_flow_node(specmcp_server))

    graph.set_entry_point("language_detect")
    graph.add_edge("language_detect", "safety_gate")
    graph.add_conditional_edges(
        "safety_gate", route_after_safety, {"escalate": "escalate", "scope_guard": "scope_guard"}
    )
    graph.add_conditional_edges(
        "scope_guard",
        route_after_scope,
        {
            "scope_refusal": "scope_refusal",
            "router": "router",
            "booking_flow": "booking_flow",
            "cancel_flow": "cancel_flow",
            "intake_flow": "intake_flow",
        },
    )
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "coverage_rag": "coverage_rag",
            "clinic_info": "clinic_info",
            "handover": "handover",
            "unclear": "unclear",
            "booking_flow": "booking_flow",
            "cancel_flow": "cancel_flow",
            "cancel_flow_reschedule": "cancel_flow_reschedule",
            "intake_flow": "intake_flow",
        },
    )
    for terminal_node in (
        "escalate",
        "scope_refusal",
        "coverage_rag",
        "clinic_info",
        "handover",
        "unclear",
        "booking_flow",
        "cancel_flow",
        "cancel_flow_reschedule",
        "intake_flow",
    ):
        graph.add_edge(terminal_node, END)

    return graph.compile(checkpointer=checkpointer)


def _reschedule_entry(cancel_node):
    def wrapped(state: ConversationState) -> dict:
        result = cancel_node(state)
        if state.get("cancel_stage") is None:
            result.setdefault("offer_rebook_after_cancel", True)
        return result

    return wrapped
