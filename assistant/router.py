"""Rule-based intent router (SPEC 7 node 4).

SPEC calls for "a small fast model, structured output" for intent
classification; this rule-based version is the no-LLM fallback used while no
API key is configured (see PROGRESS.md). Swap in an LLM-backed classifier
behind the same `classify_intent(message) -> str` signature when a key is
available, without changing any downstream node -- the graph only depends
on the returned intent string, never on how it was produced.
"""

from safety.text_normalize import normalize

INTENTS = ["book", "reschedule", "cancel", "coverage_question", "intake", "clinic_info", "handover", "unclear"]

# Order matters: more specific/urgent intents are checked before general ones
# (e.g. "cancel" before "book", since a cancellation message often also
# contains the word "appointment").
_PATTERNS: dict[str, list[str]] = {
    "handover": [
        "talk to a person", "speak to someone", "human agent", "real person",
        "أريد التحدث مع شخص", "تحويلي لموظف", "أريد موظف",
    ],
    "cancel": [
        "cancel my appointment", "cancel appointment", "cancel my booking",
        "الغاء موعد", "ألغي موعدي", "إلغاء الحجز",
    ],
    "reschedule": [
        "reschedule", "change my appointment", "move my appointment", "change my booking",
        "اعادة جدولة", "تغيير موعدي", "تأجيل الموعد",
    ],
    "intake": [
        "pre-visit intake", "pre visit intake", "fill out my intake", "start my intake",
        "intake form", "intake questionnaire", "chief complaint",
        "تسجيل بيانات ما قبل الزيارة", "نموذج الدخول", "الفحص المسبق",
    ],
    "coverage_question": [
        "does my insurance cover", "is this covered", "my coverage", "my plan cover",
        "insurance plan", "co-payment", "out-of-pocket",
        "هل يغطي تأميني", "هل تغطي خطتي", "تغطية التأمين", "الخطة التأمينية",
    ],
    "clinic_info": [
        "opening hours", "clinic hours", "where is the clinic", "parking",
        "cancellation policy", "opening time",
        "ساعات العمل", "أين العيادة", "سياسة الإلغاء", "موقع العيادة",
    ],
    "book": [
        "book an appointment", "book a slot", "i want to book", "make an appointment",
        "schedule an appointment", "book me",
        "احجز موعد", "حجز موعد", "أريد حجز", "أريد حجز موعد",
    ],
}


def classify_intent(message: str) -> str:
    norm = normalize(message)
    for intent, phrases in _PATTERNS.items():
        for phrase in phrases:
            if normalize(phrase) in norm:
                return intent
    return "unclear"
