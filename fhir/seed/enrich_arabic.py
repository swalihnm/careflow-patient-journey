"""Adds Arabic names + communication.language=ar to part of the synthetic population.

Runs in place over the *.json transaction Bundles Synthea produced. Deterministic:
which patients get enriched, and which Arabic name they get, is derived from a hash
of the patient's id, so re-running is stable and idempotent.
"""

import json
import sys
from pathlib import Path

# Plain sibling-module import, not a dotted `fhir.seed...` package path: the
# top-level `fhir` name is also used by the installed `fhir.resources` PyPI
# package (a PEP 420 namespace package), so this repo's fhir/ directory is
# deliberately never turned into an importable `fhir.*` package itself.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arabic_names import pick_name
from idhash import seed_int

DEFAULT_FRACTION = 0.4


def should_enrich(patient_id: str, fraction: float) -> bool:
    return (seed_int(patient_id) % 1000) < int(fraction * 1000)


def enrich_patient_resource(patient: dict) -> dict:
    patient_id = patient.get("id", "")
    gender = patient.get("gender", "male")
    given, family = pick_name(seed_int(patient_id), gender)

    arabic_name = {
        "use": "usual",
        "text": f"{given} {family}",
        "given": [given],
        "family": family,
    }

    existing_names = patient.get("name", [])
    for n in existing_names:
        n["use"] = "old"

    patient["name"] = [arabic_name, *existing_names]

    communications = patient.get("communication", [])
    communications.append(
        {
            "language": {
                "coding": [{"system": "urn:ietf:bcp:47", "code": "ar", "display": "Arabic"}],
                "text": "Arabic",
            },
            "preferred": True,
        }
    )
    patient["communication"] = communications
    return patient


def enrich_bundle_file(path: Path, fraction: float = DEFAULT_FRACTION) -> bool:
    """Returns True if the bundle's Patient was enriched."""
    bundle = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") != "Patient":
            continue
        if not should_enrich(resource.get("id", path.stem), fraction):
            continue
        enrich_patient_resource(resource)
        changed = True
    if changed:
        path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return changed


def enrich_directory(fhir_dir: Path, fraction: float = DEFAULT_FRACTION) -> int:
    count = 0
    for path in sorted(fhir_dir.glob("*.json")):
        if path.name.startswith(("hospitalInformation", "practitionerInformation")):
            continue
        if enrich_bundle_file(path, fraction):
            count += 1
    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fhir_dir", type=Path)
    parser.add_argument("--fraction", type=float, default=DEFAULT_FRACTION)
    args = parser.parse_args()
    n = enrich_directory(args.fhir_dir, args.fraction)
    print(f"Enriched {n} patient bundle(s) with Arabic name/language.")
