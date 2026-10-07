"""Deterministic pseudo-random assignment from an id, shared by the seed scripts
so the same patient always lands in the same clinic/plan/enrichment bucket
across re-runs (reproducible demo data, no external RNG state to track)."""

import hashlib


def seed_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


def bucket(value: str, n: int) -> int:
    """A stable integer in [0, n)."""
    return seed_int(value) % n
