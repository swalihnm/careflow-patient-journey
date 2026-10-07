"""Fixed pre-visit intake questionnaire (SPEC 7 node 7 `intake_flow` and node
8 `summarise_for_clinician`).

The clinically-reviewed question set is fixed and scripted -- asking it and
building the summary needs no LLM, which makes this the most reliably
testable part of the graph. It's also arguably the *right* design for node
8's "no interpretation" requirement: a template listing the patient's own
words verbatim can't introduce a paraphrase-driven distortion the way an
LLM summary could.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

QUESTIONS = [
    {
        "id": "chief_complaint",
        "text_en": "What is the main reason for your visit today?",
        "text_ar": "ما هو السبب الرئيسي لزيارتك اليوم؟",
    },
    {
        "id": "duration",
        "text_en": "How long have you been experiencing this?",
        "text_ar": "منذ متى وأنت تعاني من هذا؟",
    },
    {
        "id": "severity",
        "text_en": "On a scale of 1 to 10, how would you rate the severity?",
        "text_ar": "على مقياس من 1 إلى 10، كيف تقيّم شدة الأعراض؟",
    },
    {
        "id": "allergies",
        "text_en": "Do you have any known allergies?",
        "text_ar": "هل لديك أي حساسية معروفة؟",
    },
]


@dataclass
class IntakeState:
    answers: dict[str, str] = field(default_factory=dict)

    @property
    def next_question(self) -> dict | None:
        for q in QUESTIONS:
            if q["id"] not in self.answers:
                return q
        return None

    @property
    def is_complete(self) -> bool:
        return self.next_question is None

    def record_answer(self, question_id: str, answer: str) -> None:
        self.answers[question_id] = answer


def build_questionnaire_response(patient_id: str, state: IntakeState) -> dict:
    """FHIR QuestionnaireResponse, one item per question, patient's own words verbatim."""
    return {
        "resourceType": "QuestionnaireResponse",
        "id": f"intake-{patient_id}-{int(datetime.now(UTC).timestamp())}",
        "status": "completed",
        "subject": {"reference": f"Patient/{patient_id}"},
        "authored": datetime.now(UTC).isoformat(),
        "item": [
            {
                "linkId": q["id"],
                "text": q["text_en"],
                "answer": [{"valueString": state.answers[q["id"]]}],
            }
            for q in QUESTIONS
            if q["id"] in state.answers
        ],
    }


def build_clinician_summary(state: IntakeState) -> str:
    """A neutral structured summary in the patient's own words -- no
    interpretation, no diagnosis (SPEC clinical safety rule 1)."""
    lines = ["Pre-visit intake summary (patient's own words, not a diagnosis):"]
    for q in QUESTIONS:
        answer = state.answers.get(q["id"])
        if answer:
            lines.append(f"- {q['text_en']}: {answer}")
    return "\n".join(lines)
