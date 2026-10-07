"""Rule-based scope guard (SPEC 8.1): catches requests for diagnosis,
medication advice/dosage, or test-result interpretation -- the three things
clinical safety rule 1 says the assistant must never do, whatever else is
happening in the conversation.

Same design principle as red_flag.py: broad, recall-oriented keyword/phrase
matching. A kind refusal is cheap; missing a diagnosis request is not.
"""

from dataclasses import dataclass

from safety.text_normalize import normalize

DIAGNOSIS_PHRASES_EN = [
    "what disease do i have", "do i have cancer", "do i have diabetes",
    "what's wrong with me", "what is wrong with me", "am i diabetic",
    "diagnose me", "what condition do i have", "could this be",
    "is this a symptom of", "what illness is this", "do you think i have",
    # Added after a dedicated prompt-injection eval (evals/injection/messages.yaml)
    # found these paraphrases -- mostly the same request wrapped in
    # "ignore your instructions" / fake-admin / roleplay framing -- slipped
    # past the original list. General phrases, not copies of the eval
    # messages themselves, so this generalizes past that specific set.
    "tell me what disease", "diagnose my symptoms", "diagnose the patient",
    "what's my diagnosis", "what is my diagnosis", "my diagnosis is",
    "medical diagnosis", "mean something serious", "means something serious",
    "matches these symptoms", "match these symptoms", "symptoms described",
    "what illness causes", "illness causes these symptoms",
]
DIAGNOSIS_PHRASES_AR = [
    "ما هو مرضي", "هل لدي سرطان", "هل أنا مصاب بالسكري", "ما الذي أعاني منه",
    "شخص حالتي", "ما هو المرض الذي أعاني منه", "يمكنك تشخيص", "هل تعتقد أن لدي",
    # Same injection-eval hardening as the English list above.
    "تشخيصي", "بتشخيص", "شخص الحالة",
]
DIAGNOSIS_PHRASES_ARABIZI = ["ash marathi"]

MEDICATION_PHRASES_EN = [
    "how many mg should i take", "what dose of", "should i take ibuprofen",
    "should i increase my dose", "can i stop taking my medication",
    "what medication should i take", "prescribe me", "can you prescribe",
    "should i take paracetamol", "is it safe to combine",
    "how much medicine should i take", "what pill should i take", "how many mg",
    # Injection-eval hardening (see DIAGNOSIS_PHRASES_EN's comment above).
    "medication dose should i take", "prescribe medication", "dose should i take",
]
MEDICATION_PHRASES_AR = [
    "كم ملغ يجب أن آخذ", "ما هي الجرعة المناسبة", "هل يمكنني التوقف عن الدواء",
    "ما هو الدواء الذي يجب أن آخذه", "صف لي دواء", "جرعتي الحالية من الدواء",
    "الجرعة الآمنة", "كم ملغ من",
]
MEDICATION_PHRASES_ARABIZI = ["kam mg", "yjb akhoth"]

TEST_INTERPRETATION_PHRASES_EN = [
    "what does my blood test mean", "interpret my lab results", "what does my a1c mean",
    "is this test result normal", "what does my mri show", "explain my test results",
    "what do these lab values mean", "is my x-ray okay",
]
TEST_INTERPRETATION_PHRASES_AR = [
    "ماذا يعني تحليل الدم", "فسر نتائج التحاليل", "هل نتيجة التحليل طبيعية",
    "ماذا تظهر الأشعة", "اشرح لي نتائج فحوصاتي", "فسر لي نتائج",
    "تفسير تقرير الأشعة", "تعنيه نتيجة فحص", "القيم المخبرية", "تفسير نتيجة فحص",
    # Injection-eval hardening: singular "نتيجة" (result), not just plural
    # "نتائج" (results) -- a real gap, not a hypothetical one.
    "فسر لي نتيجة",
]
TEST_INTERPRETATION_PHRASES_ARABIZI = ["ash ya3ni tahlil"]
TEST_INTERPRETATION_PHRASES_EN += [
    "cholesterol numbers mean", "interpret my ultrasound report", "a1c result mean",
    "interpret my recent", "interpret my blood test", "interpret my test result",
    "test results are normal", "results are normal",
]

CATEGORY_PHRASES = {
    "diagnosis": DIAGNOSIS_PHRASES_EN + DIAGNOSIS_PHRASES_AR + DIAGNOSIS_PHRASES_ARABIZI,
    "medication": MEDICATION_PHRASES_EN + MEDICATION_PHRASES_AR + MEDICATION_PHRASES_ARABIZI,
    "test_interpretation": (
        TEST_INTERPRETATION_PHRASES_EN + TEST_INTERPRETATION_PHRASES_AR + TEST_INTERPRETATION_PHRASES_ARABIZI
    ),
}


@dataclass(frozen=True)
class ScopeViolation:
    is_violation: bool
    category: str | None = None
    matched_phrase: str | None = None


class ScopeGuard:
    def __init__(self):
        self._index: list[tuple[str, str, str]] = []  # (normalized_phrase, category, raw_phrase)
        for category, phrases in CATEGORY_PHRASES.items():
            for phrase in phrases:
                norm = normalize(phrase)
                if norm:
                    self._index.append((norm, category, phrase))
        self._index.sort(key=lambda t: -len(t[0]))

    def check(self, message: str) -> ScopeViolation:
        norm = normalize(message)
        for norm_phrase, category, raw_phrase in self._index:
            if norm_phrase in norm:
                return ScopeViolation(True, category, raw_phrase)
        return ScopeViolation(is_violation=False)


_default_guard: ScopeGuard | None = None


def get_default_guard() -> ScopeGuard:
    global _default_guard
    if _default_guard is None:
        _default_guard = ScopeGuard()
    return _default_guard


def check_scope(message: str) -> ScopeViolation:
    return get_default_guard().check(message)
