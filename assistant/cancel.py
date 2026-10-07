"""Cancel (and reschedule, treated as cancel-then-rebook -- see graph.py's
module docstring for that scope simplification) flow helpers. specmcp-backed
(search_appointments / cancel_appointment), no LLM needed.
"""

from dataclasses import dataclass, field

from assistant.booking import format_time


@dataclass(frozen=True)
class AppointmentOption:
    id: str
    start: str
    end: str
    # The full original Appointment resource, kept as-is: FHIR PUT replaces
    # the whole resource, so cancelling has to send the complete original
    # back with only `status` changed, not a minimal reconstruction that
    # would silently drop `participant`/`slot`/everything else.
    resource: dict = field(default_factory=dict)


def extract_appointment_options(search_result: dict) -> list[AppointmentOption]:
    options = []
    for entry in search_result.get("entry", []):
        resource = entry.get("resource", {})
        # Filtering on `resource["status"]` here (the freshly-returned resource
        # body), not on a `status=booked` *search* parameter, is deliberate:
        # verified directly against a live HAPI server that its `status`
        # token search index can stay stale well after a write actually
        # commits -- a `status=booked` search kept matching an appointment
        # for 10+ seconds and several more writes after it had genuinely been
        # cancelled, even though every returned resource body already showed
        # `status: cancelled` correctly. The resource body is always current;
        # the search-parameter match is what lags. See search_appointments_params.
        if resource.get("status") != "booked":
            continue
        options.append(
            AppointmentOption(
                id=resource["id"], start=resource.get("start", ""), end=resource.get("end", ""), resource=resource
            )
        )
    # Soonest first, so "1" is the most likely one a patient means.
    options.sort(key=lambda o: o.start)
    return options


def format_appointment_options(options: list[AppointmentOption], language: str) -> str:
    if language == "ar":
        header = "وجدت هذه المواعيد القادمة، يرجى الرد برقم الموعد الذي تريد إلغاءه:"
        lines = [f"{i + 1}. {format_time(o.start, language)}" for i, o in enumerate(options)]
    else:
        header = "I found these upcoming appointments -- reply with the number of the one to cancel:"
        lines = [f"{i + 1}. {format_time(o.start, language)}" for i, o in enumerate(options)]
    return "\n".join([header, *lines])


def cancel_confirm_prompt(option: AppointmentOption, language: str) -> str:
    time_str = format_time(option.start, language)
    if language == "ar":
        return f"هل تريد تأكيد إلغاء موعدك في {time_str}؟ (نعم/لا)"
    return f"Confirm cancelling your appointment on {time_str}? (yes/no)"


def cancel_confirmed_message(option: AppointmentOption, language: str, offer_rebook: bool) -> str:
    time_str = format_time(option.start, language)
    if language == "ar":
        base = f"تم إلغاء موعدك في {time_str}."
        if offer_rebook:
            base += " إذا أردت حجز موعد جديد، فقط أخبرني."
        return base
    base = f"Your appointment on {time_str} has been cancelled."
    if offer_rebook:
        base += " If you'd like to book a new time, just let me know."
    return base


def no_appointments_message(language: str) -> str:
    if language == "ar":
        return "لم أجد أي مواعيد قادمة مرتبطة بك."
    return "I couldn't find any upcoming appointments for you."


def build_cancelled_appointment_resource(option: AppointmentOption) -> dict:
    """The full original resource with only `status` changed -- see
    AppointmentOption's docstring for why a minimal reconstruction would be wrong."""
    return {**option.resource, "status": "cancelled"}


def search_appointments_params(patient_id: str) -> dict:
    # No `status` filter here on purpose -- see extract_appointment_options's
    # comment: filtering by status is done client-side on the fresh resource
    # body instead, since the server-side `status` search match can lag.
    # `_count: 100` guards against HAPI's default 20-per-page search result:
    # a patient with more than 20 total (not just booked) appointments ever
    # created would otherwise silently have older ones invisible to this
    # search -- confirmed directly against a long-lived test patient that
    # had accumulated 25+ appointments across repeated runs. This only works
    # because `_count` is declared as a query parameter for `search_appointments`
    # in fhir/openapi/fhir.yaml -- specmcp's fhir_client.py silently drops any
    # param not declared there (confirmed directly: this exact `_count` was a
    # no-op for a while until the OpenAPI spec itself was fixed, since specmcp
    # is spec-driven by design, not params-passthrough).
    return {"patient": f"Patient/{patient_id}", "_count": 100}
