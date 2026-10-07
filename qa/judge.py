"""QA judge (SPEC 8.2): an LLM scores each finished conversation against
qa/rubric.py's rubric. Uses a different prompt (and ideally a different
model) than the assistant itself -- an independent auditor, not the same
component grading its own work. Genuinely LLM-dependent: see PROGRESS.md for
what that means in an environment with no key configured (raises
LLMNotConfigured via trustcore.gateway, same as every other LLM-dependent
path in this repo).
"""

import json
from dataclasses import dataclass

from trustcore.gateway import complete

from qa.rubric import JUDGE_SYSTEM_PROMPT, RUBRIC_VERSION, format_transcript


@dataclass(frozen=True)
class JudgeScore:
    rubric_version: str
    safety: str  # "pass" | "fail"
    safety_justification: str
    accuracy: int
    accuracy_justification: str
    grounding: int
    grounding_justification: str
    privacy: str  # "pass" | "fail"
    privacy_justification: str
    tone_and_empathy: int
    tone_and_empathy_justification: str
    language_quality: int
    language_quality_justification: str
    failure_tags: list[str]
    raw_model: str


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.removeprefix("json")
    return json.loads(text.strip())


def score_conversation(turns: list[dict], actor: str = "qa-judge") -> JudgeScore:
    transcript = format_transcript(turns)
    response = complete(
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Transcript:\n\n{transcript}"},
        ],
        actor=actor,
        max_tokens=2000,
        temperature=0.0,
    )
    data = _parse_json_response(response.text)

    return JudgeScore(
        rubric_version=RUBRIC_VERSION,
        safety=data["safety"],
        safety_justification=data["safety_justification"],
        accuracy=int(data["accuracy"]),
        accuracy_justification=data["accuracy_justification"],
        grounding=int(data["grounding"]),
        grounding_justification=data["grounding_justification"],
        privacy=data["privacy"],
        privacy_justification=data["privacy_justification"],
        tone_and_empathy=int(data["tone_and_empathy"]),
        tone_and_empathy_justification=data["tone_and_empathy_justification"],
        language_quality=int(data["language_quality"]),
        language_quality_justification=data["language_quality_justification"],
        failure_tags=list(data.get("failure_tags", [])),
        raw_model=response.model,
    )
