"""fhir/seed/*.py are plain scripts (not an importable `fhir.seed` package --
see the note in enrich_arabic.py about the fhir.resources namespace collision),
so tests reach them the same way the scripts reach each other: by adding the
directory to sys.path."""

import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parents[2] / "fhir" / "seed"
sys.path.insert(0, str(SEED_DIR))

from arabic_names import pick_name
from enrich_arabic import enrich_patient_resource, should_enrich
from idhash import bucket, seed_int


def test_seed_int_deterministic():
    assert seed_int("patient-1") == seed_int("patient-1")
    assert seed_int("patient-1") != seed_int("patient-2")


def test_bucket_in_range():
    for pid in ["a", "b", "c", "patient-42"]:
        assert 0 <= bucket(pid, 3) < 3


def test_should_enrich_is_deterministic_and_roughly_matches_fraction():
    ids = [f"patient-{i}" for i in range(2000)]
    enriched = [pid for pid in ids if should_enrich(pid, 0.4)]
    # deterministic
    assert enriched == [pid for pid in ids if should_enrich(pid, 0.4)]
    # roughly 40% (loose bound -- this is a hash bucket, not a precise sampler)
    assert 0.30 < len(enriched) / len(ids) < 0.50


def test_pick_name_returns_from_curated_lists():
    given, family = pick_name(0, "female")
    assert isinstance(given, str) and given
    assert isinstance(family, str) and family


def test_enrich_patient_resource_adds_arabic_name_and_language():
    patient = {
        "id": "test-1",
        "gender": "female",
        "name": [{"use": "official", "given": ["Jane"], "family": "Doe"}],
    }
    enriched = enrich_patient_resource(patient)

    assert enriched["name"][0]["use"] == "usual"
    assert enriched["name"][1]["use"] == "old"  # original name demoted, not lost
    assert enriched["name"][1]["family"] == "Doe"

    langs = [c["language"]["coding"][0]["code"] for c in enriched["communication"]]
    assert "ar" in langs
