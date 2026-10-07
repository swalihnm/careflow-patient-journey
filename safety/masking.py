"""PII/PHI masking before logging and before the LLM where not needed (SPEC 8.1).

Presidio's built-in recognizers catch names/emails/generic phone numbers;
two custom pattern recognizers add the UAE-specific patterns Presidio has no
built-in concept of: a synthetic Emirates-ID-style identifier and UAE mobile
numbers. Analyzer is expensive to construct (loads the spaCy model), so it's
built once and reused.

Known gap: Presidio's NLP engine here is only configured for English, so
PERSON-name detection only works on English text -- the regex-based Emirates
ID / UAE phone recognizers are language-independent and still catch those in
Arabic text, but Arabic name detection would need a second spaCy pipeline
(e.g. Arabic transformers or CAMeL Tools) not set up here. Document this
rather than silently under-masking Arabic conversations.
"""

from dataclasses import dataclass

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

# Synthetic Emirates ID pattern: 784-YYYY-XXXXXXX-X (15 digits, 784 = UAE
# country prefix). "Synthetic" per SPEC 5's field-masking table -- this never
# encodes a real Emirates ID, only Synthea-style synthetic identifiers shaped
# like one.
EMIRATES_ID_REGEX = r"\b784-?\d{4}-?\d{7}-?\d\b"

# UAE mobile numbers: +971 5X XXX XXXX or 05X XXX XXXX, prefixes 050/052/054/055/056/058.
UAE_PHONE_REGEX = r"\b(?:\+?971[-\s]?0?|0)5[024568][-\s]?\d{3}[-\s]?\d{4}\b"

EMIRATES_ID_ENTITY = "UAE_EMIRATES_ID"
UAE_PHONE_ENTITY = "UAE_PHONE_NUMBER"

_DEFAULT_ENTITIES = [
    # Deliberately excludes DATE_TIME: appointment dates/times are
    # operationally necessary content for a booking assistant, not the PHI
    # this spec's masking rule targets (Emirates ID, phone, name).
    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION",
    "CREDIT_CARD", "IBAN_CODE", EMIRATES_ID_ENTITY, UAE_PHONE_ENTITY,
]


def _build_analyzer() -> AnalyzerEngine:
    analyzer = AnalyzerEngine()

    analyzer.registry.add_recognizer(
        PatternRecognizer(
            supported_entity=EMIRATES_ID_ENTITY,
            patterns=[Pattern(name="emirates_id", regex=EMIRATES_ID_REGEX, score=0.9)],
        )
    )
    analyzer.registry.add_recognizer(
        PatternRecognizer(
            supported_entity=UAE_PHONE_ENTITY,
            patterns=[Pattern(name="uae_phone", regex=UAE_PHONE_REGEX, score=0.85)],
        )
    )
    return analyzer


@dataclass(frozen=True)
class MaskResult:
    masked_text: str
    entities_found: list[str]  # entity types found, e.g. ["PERSON", "UAE_PHONE_NUMBER"]


class Masker:
    def __init__(self):
        self._analyzer = _build_analyzer()
        self._anonymizer = AnonymizerEngine()

    def mask(self, text: str) -> MaskResult:
        """`language` is intentionally not a parameter -- see the module
        docstring: the analyzer is only configured for English NLP, and
        passing another language code to Presidio would raise, not degrade
        gracefully."""
        if not text:
            return MaskResult(masked_text=text, entities_found=[])

        results = self._analyzer.analyze(text=text, entities=_DEFAULT_ENTITIES, language="en")
        if not results:
            return MaskResult(masked_text=text, entities_found=[])

        anonymized = self._anonymizer.anonymize(text=text, analyzer_results=results)
        entities_found = sorted({r.entity_type for r in results})
        return MaskResult(masked_text=anonymized.text, entities_found=entities_found)


_default_masker: Masker | None = None


def get_default_masker() -> Masker:
    global _default_masker
    if _default_masker is None:
        _default_masker = Masker()
    return _default_masker


def mask_text(text: str) -> MaskResult:
    return get_default_masker().mask(text)
