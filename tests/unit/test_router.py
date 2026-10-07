"""Rule-based intent router (SPEC 7 node 4). Every intent in INTENTS (other
than "unclear", the fallback) must have at least one real example that
classifies correctly -- this is the test that would have caught "intake"
being declared in INTENTS but never given any patterns (a real bug found
while wiring intake_flow into the graph: "I need to do my pre-visit intake"
silently fell through to "unclear" forever).
"""

import pytest

from assistant.router import INTENTS, classify_intent

EXAMPLES = {
    "book": "I want to book an appointment",
    "reschedule": "Can I reschedule my appointment",
    "cancel": "I need to cancel my appointment",
    "coverage_question": "Does my insurance cover physiotherapy?",
    "intake": "I need to do my pre-visit intake",
    "clinic_info": "What are your opening hours?",
    "handover": "I want to talk to a person",
}

EXAMPLES_AR = {
    "book": "أريد حجز موعد",
    "cancel": "أحتاج الغاء موعد",
    "coverage_question": "هل يغطي تأميني هذا؟",
    "clinic_info": "ما هي ساعات العمل؟",
    "handover": "أريد التحدث مع شخص",
}


def test_every_declared_intent_except_unclear_has_a_working_example():
    """Regression guard: a real bug had "intake" listed in INTENTS with zero
    patterns in _PATTERNS, so it could never be classified -- this test
    fails loudly if that happens again for any intent."""
    non_fallback_intents = [i for i in INTENTS if i != "unclear"]
    assert set(non_fallback_intents) == set(EXAMPLES.keys())
    for intent, message in EXAMPLES.items():
        assert classify_intent(message) == intent, f"{intent!r} example {message!r} misclassified"


@pytest.mark.parametrize("intent,message", EXAMPLES.items())
def test_english_examples(intent, message):
    assert classify_intent(message) == intent


@pytest.mark.parametrize("intent,message", EXAMPLES_AR.items())
def test_arabic_examples(intent, message):
    assert classify_intent(message) == intent


def test_unrelated_message_is_unclear():
    assert classify_intent("hmm okay") == "unclear"
    assert classify_intent("what a nice day") == "unclear"
