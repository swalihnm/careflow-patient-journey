"""Text normalization shared by every rule-based safety check, so the same
message normalizes the same way whether it's being checked for a red flag,
a scope violation, or logged for audit.

Handles English casing/whitespace and the common Arabic-script variations
(diacritics, alef/ya/ta-marbuta forms) that would otherwise make a keyword
match miss trivially different spellings of the same word.
"""

import re
import unicodedata

_ARABIC_DIACRITICS = re.compile(r"[ً-ٰٟۖ-ۭ]")


def normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _ARABIC_DIACRITICS.sub("", text)

    # Common Arabic orthographic variants that should match as the same word.
    text = text.translate(
        str.maketrans(
            {
                "أ": "ا", "إ": "ا", "آ": "ا",
                "ى": "ي",
                "ة": "ه",
                "ؤ": "و",
                "ئ": "ي",
            }
        )
    )

    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text
