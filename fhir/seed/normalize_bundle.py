"""Rewrites Synthea's default POST+urn:uuid transaction bundles into PUT+explicit-id
bundles.

Synthea's FHIR exporter creates each resource with `request.method: POST` and a
`urn:uuid:...` fullUrl, letting the server assign the final id -- other entries
in the same bundle that reference it get rewritten by the server during transaction
processing, but *we* never see that server-assigned id. Our own code (Coverage
generation, and re-running `make seed` idempotently) needs to know each patient's
id upfront, so this rewrites every entry to `PUT {ResourceType}/{id}` using the id
Synthea already put in the resource body, and follows every `urn:uuid:...`
reference anywhere in the bundle to the same explicit `ResourceType/id` form.
"""

import json
from pathlib import Path
from typing import Any


def _build_uuid_map(bundle: dict) -> dict[str, str]:
    uuid_map: dict[str, str] = {}
    for entry in bundle.get("entry", []):
        full_url = entry.get("fullUrl")
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType")
        rid = resource.get("id")
        if full_url and full_url.startswith("urn:uuid:") and rtype and rid:
            uuid_map[full_url] = f"{rtype}/{rid}"
    return uuid_map


def _rewrite_references(obj: Any, uuid_map: dict[str, str]) -> None:
    if isinstance(obj, dict):
        ref = obj.get("reference")
        if isinstance(ref, str) and ref in uuid_map:
            obj["reference"] = uuid_map[ref]
        for value in obj.values():
            _rewrite_references(value, uuid_map)
    elif isinstance(obj, list):
        for item in obj:
            _rewrite_references(item, uuid_map)


def normalize_bundle(bundle: dict) -> dict:
    uuid_map = _build_uuid_map(bundle)

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType")
        rid = resource.get("id")
        if rtype and rid:
            entry["fullUrl"] = f"{rtype}/{rid}"
            entry["request"] = {"method": "PUT", "url": f"{rtype}/{rid}"}

    _rewrite_references(bundle, uuid_map)
    return bundle


def normalize_file(path: Path) -> None:
    bundle = json.loads(path.read_text(encoding="utf-8"))
    normalize_bundle(bundle)
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")


def normalize_directory(fhir_dir: Path) -> int:
    count = 0
    for path in sorted(fhir_dir.glob("*.json")):
        normalize_file(path)
        count += 1
    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fhir_dir", type=Path)
    args = parser.parse_args()
    n = normalize_directory(args.fhir_dir)
    print(f"Normalized {n} bundle file(s) to PUT+explicit-id.")
