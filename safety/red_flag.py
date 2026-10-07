"""Rule-based bilingual red-flag detection (SPEC 8.1 stage 1).

This is the primary, non-negotiable safety mechanism: SPEC 8.1 says escalate
if EITHER the rules OR an LLM classifier fires, and the eval set must hit
100% recall. Built to reach that 100% recall on its own -- a later LLM
classifier (Phase 3, needs a real API key, see PROGRESS.md) is a
supplementary catch for paraphrases this rule set misses, not something the
100%-recall guarantee depends on.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from safety.text_normalize import normalize

PROTOCOL_PATH = Path(__file__).resolve().parent / "protocol.yaml"


@dataclass(frozen=True)
class RedFlagMatch:
    is_red_flag: bool
    category: str | None = None
    escalation: str | None = None  # "emergency" | "crisis"
    matched_keyword: str | None = None
    label_en: str | None = None


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class RedFlagDetector:
    def __init__(self, protocol: dict | None = None):
        self.protocol = protocol or load_protocol()
        # (normalized_keyword, category_id, escalation, label_en, raw_keyword)
        self._index: list[tuple[str, str, str, str, str]] = []
        for cat_id, cat in self.protocol.get("categories", {}).items():
            escalation = cat.get("escalation", "emergency")
            label_en = cat.get("label_en", cat_id)
            for key in ("keywords_en", "keywords_ar", "keywords_dialect_arabizi"):
                for kw in cat.get(key, []) or []:
                    norm_kw = normalize(kw)
                    if norm_kw:
                        self._index.append((norm_kw, cat_id, escalation, label_en, kw))
        # Longest keyword first: mostly cosmetic (which category gets
        # reported when a message matches more than one), but prefers the
        # more specific phrase.
        self._index.sort(key=lambda t: -len(t[0]))

    def check(self, message: str) -> RedFlagMatch:
        norm = normalize(message)
        for norm_kw, cat_id, escalation, label_en, raw_kw in self._index:
            if norm_kw in norm:
                return RedFlagMatch(True, cat_id, escalation, raw_kw, label_en)
        return RedFlagMatch(is_red_flag=False)


_default_detector: RedFlagDetector | None = None


def get_default_detector() -> RedFlagDetector:
    global _default_detector
    if _default_detector is None:
        _default_detector = RedFlagDetector()
    return _default_detector


def check_red_flag(message: str) -> RedFlagMatch:
    return get_default_detector().check(message)
