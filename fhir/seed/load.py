"""Orchestrates Phase 1 seeding: Synthea patients (+ Arabic enrichment) plus the
hand-authored clinic/coverage resources, all posted to HAPI FHIR as transaction
bundles.

Usage:
    python -m fhir.seed.load --count 300               # dev scale (make seed)
    python -m fhir.seed.load --count 2000               # full scale (make seed-full)
    python -m fhir.seed.load --count 300 --skip-synthea  # reuse existing output/
"""

import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clinic_resources
import coverage
import enrich_arabic
import normalize_bundle
import synthea_runner

DEFAULT_BASE_URL = os.environ.get("CAREFLOW_FHIR_BASE_URL", "http://localhost:8210/fhir")
CHUNK_SIZE = 200


def to_transaction_bundle(resources: list[dict]) -> dict:
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "fullUrl": f"{r['resourceType']}/{r['id']}",
                "resource": r,
                "request": {"method": "PUT", "url": f"{r['resourceType']}/{r['id']}"},
            }
            for r in resources
        ],
    }


def _post_bundle(client: httpx.Client, base_url: str, bundle: dict) -> None:
    resp = client.post(base_url, json=bundle)
    if resp.status_code >= 400:
        raise RuntimeError(f"FHIR transaction failed ({resp.status_code}): {resp.text[:2000]}")


def post_resources(client: httpx.Client, base_url: str, resources: list[dict], label: str) -> None:
    total = len(resources)
    for i in range(0, total, CHUNK_SIZE):
        chunk = resources[i : i + CHUNK_SIZE]
        _post_bundle(client, base_url, to_transaction_bundle(chunk))
        print(f"  {label}: {min(i + CHUNK_SIZE, total)}/{total}", file=sys.stderr)


def post_synthea_bundles(client: httpx.Client, base_url: str, fhir_dir: Path) -> list[str]:
    """POSTs each Synthea-generated (and Arabic-enriched) patient bundle as-is —
    Synthea already wrote valid transaction Bundles with per-entry request
    method/url. Returns the list of patient ids found, for Coverage generation.

    hospitalInformation*.json / practitionerInformation*.json are separate
    aggregate bundles (all Organizations / all Practitioners) that per-patient
    bundles reference via conditional-update match URLs (e.g. "Practitioner?
    identifier=...|9999951590"); they must be posted first or those references
    fail to resolve.
    """
    all_files = sorted(fhir_dir.glob("*.json"))
    info_files = [p for p in all_files if p.name.startswith(("hospitalInformation", "practitionerInformation"))]
    patient_files = [p for p in all_files if p not in info_files]

    for path in info_files:
        bundle = json.loads(path.read_text(encoding="utf-8"))
        _post_bundle(client, base_url, bundle)
        print(f"  posted {path.name}", file=sys.stderr)

    patient_ids: list[str] = []
    for n, path in enumerate(patient_files, start=1):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Patient":
                patient_ids.append(resource["id"])
        _post_bundle(client, base_url, bundle)
        if n % 25 == 0 or n == len(patient_files):
            print(f"  synthea patients: {n}/{len(patient_files)}", file=sys.stderr)
    return patient_ids


def run(count: int, state: str, seed: int | None, base_url: str, skip_synthea: bool, max_age: int = 75) -> None:
    if skip_synthea and synthea_runner.OUTPUT_DIR.joinpath("fhir").exists():
        fhir_dir = synthea_runner.OUTPUT_DIR / "fhir"
        print(f"Reusing existing Synthea output at {fhir_dir}", file=sys.stderr)
    else:
        fhir_dir = synthea_runner.run_synthea(count, state, seed, max_age)

    n_normalized = normalize_bundle.normalize_directory(fhir_dir)
    print(f"Normalized {n_normalized} bundle file(s) to PUT+explicit-id.", file=sys.stderr)

    n_enriched = enrich_arabic.enrich_directory(fhir_dir)
    print(f"Arabic-enriched {n_enriched} patient(s).", file=sys.stderr)

    # Seeding is a one-off admin operation, not a latency-sensitive request --
    # some patient bundles run to several MB, so a generous timeout beats a
    # spurious failure partway through a long run.
    with httpx.Client(timeout=300.0) as client:
        print("Posting Synthea patient bundles...", file=sys.stderr)
        patient_ids = post_synthea_bundles(client, base_url, fhir_dir)

        print("Posting clinic resources (organizations, practitioners, schedules, slots)...", file=sys.stderr)
        post_resources(client, base_url, clinic_resources.build_all(), "clinic resources")

        print("Posting payer organization + insurance plans...", file=sys.stderr)
        post_resources(
            client,
            base_url,
            [coverage.build_payer_organization(), *coverage.build_insurance_plans()],
            "insurance plans",
        )

        print("Posting Coverage resources...", file=sys.stderr)
        coverages = [coverage.build_coverage_for_patient(pid) for pid in patient_ids]
        post_resources(client, base_url, coverages, "coverage")

    print(f"Done. Loaded {len(patient_ids)} patients.", file=sys.stderr)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--state", default="Massachusetts")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--skip-synthea", action="store_true")
    parser.add_argument("--max-age", type=int, default=75)
    args = parser.parse_args()
    run(args.count, args.state, args.seed, args.base_url, args.skip_synthea, args.max_age)
