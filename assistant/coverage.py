"""Coverage/policy question answering (SPEC 7 node 6 `coverage_rag`).

Retrieval is real (rag/store.py: local multilingual embeddings, pgvector)
regardless of whether an LLM is configured. Without an LLM, the answer is
extractive -- the single most relevant chunk, quoted directly with its
citation. That's accurate and grounded by construction (SPEC 7 acceptance
criteria: "Coverage answers cite the plan section"), if less conversational
than an LLM paraphrase would be. When trustcore.gateway is configured, a
graph node can additionally ask it to smooth the phrasing of the same
retrieved chunk -- never to add facts beyond what was retrieved.
"""

from dataclasses import dataclass

from rag.store import RetrievedChunk, query

# Cosine distance (1 - cosine similarity) above which the match is too weak
# to answer from -- calibrated against this corpus's real query/chunk
# distances, not a guess (see tests/unit/test_coverage_rag.py).
CONFIDENCE_THRESHOLD = 0.65


@dataclass(frozen=True)
class CoverageAnswer:
    grounded: bool
    text: str
    citation: str | None
    chunk: RetrievedChunk | None


def answer_coverage_question(question: str, language: str, k: int = 3) -> CoverageAnswer:
    # Same-language chunks first (see rag/store.py's query() docstring for
    # why) -- only fall back to the cross-lingual search if nothing in the
    # patient's own language is close enough.
    results = query(question, k=k, language=language)
    if not results or results[0].distance > CONFIDENCE_THRESHOLD:
        results = query(question, k=k)
    if not results or results[0].distance > CONFIDENCE_THRESHOLD:
        handover = (
            "لست متأكدا تماما من ذلك -- دعني أوصلك بشخص يمكنه تأكيد تغطيتك."
            if language == "ar"
            else "I'm not fully sure about that -- let me connect you with someone who can confirm your coverage."
        )
        return CoverageAnswer(grounded=False, text=handover, citation=None, chunk=None)

    best = results[0]
    citation = f"{best.document} — {best.section} ({best.version_date})"
    text = f"{best.content}\n\n(المصدر: {citation})" if language == "ar" else f"{best.content}\n\n(Source: {citation})"

    return CoverageAnswer(grounded=True, text=text, citation=citation, chunk=best)
