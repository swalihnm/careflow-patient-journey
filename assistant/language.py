"""Language detection (SPEC 7, node 1: `language_detect`) -- no LLM needed.

A Unicode-range check for Arabic script runs first: it's instant and exact
for anything containing Arabic characters, which covers Modern Standard
Arabic and Gulf dialect written in Arabic script. `langdetect` is the
fallback for Latin-script text (English, or Arabizi -- Arabic transliterated
into Latin letters, which langdetect can't reliably separate from English by
itself, so Arabizi is treated as English for reply-language purposes: the
assistant replies in Latin script either way, which is what an Arabizi
speaker expects, not literary Arabic script back).
"""

import re
from dataclasses import dataclass

_ARABIC_SCRIPT_RE = re.compile(r"[؀-ۿݐ-ݿ]")


@dataclass(frozen=True)
class LanguageResult:
    language: str  # "ar" | "en"
    is_mixed: bool  # both Arabic script and Latin letters present
    method: str  # "arabic_script" | "langdetect" | "default"


def detect_language(text: str) -> LanguageResult:
    if not text or not text.strip():
        return LanguageResult(language="en", is_mixed=False, method="default")

    has_arabic_script = bool(_ARABIC_SCRIPT_RE.search(text))
    has_latin_letters = bool(re.search(r"[A-Za-z]", text))

    if has_arabic_script:
        return LanguageResult(language="ar", is_mixed=has_latin_letters, method="arabic_script")

    from langdetect import DetectorFactory, LangDetectException, detect

    try:
        DetectorFactory.seed = 0  # deterministic
        detected = detect(text)
        language = "ar" if detected == "ar" else "en"
        return LanguageResult(language=language, is_mixed=False, method="langdetect")
    except LangDetectException:
        # Too short/ambiguous for langdetect to call (e.g. "ok", "hi") --
        # defaulting to English is the safer guess for Latin-script input.
        return LanguageResult(language="en", is_mixed=False, method="default")
