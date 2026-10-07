"""Local embedding model for the policy RAG -- no LLM API key needed for
retrieval (SPEC's RAG store is pgvector; this is what fills and queries it).

paraphrase-multilingual-MiniLM-L12-v2 is used specifically because it's
trained for cross-lingual semantic similarity, so an Arabic question can
retrieve an English chunk (or vice versa) by meaning, not just by shared
vocabulary -- needed for "retrieval searches both [languages]" (SPEC 7).
"""

from functools import lru_cache

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed(texts: list[str]) -> list[list[float]]:
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
