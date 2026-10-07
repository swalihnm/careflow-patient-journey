"""Downloads Synthea (the real tool, not a custom stand-in) and runs it to produce
per-patient FHIR R4 transaction Bundles.

Synthea's own clinical/demographic modules are US-flavoured (it has no Dubai/UAE
module); that's fine per SPEC section 5 — Synthea supplies clinically-realistic
structure (Encounter/Condition/MedicationRequest history), and enrich_arabic.py
layers Arabic names/language on top for part of the population afterwards, and
clinic_resources.py adds the two fictional "Gulf Horizon Clinics" Organizations,
practitioners, schedules and slots that patients actually book through.
"""

import shutil
import subprocess
import sys
from pathlib import Path

JAR_URL = "https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar"

HERE = Path(__file__).resolve().parent
SYNTHEA_DIR = HERE / "synthea"
JAR_PATH = SYNTHEA_DIR / "synthea-with-dependencies.jar"
OUTPUT_DIR = SYNTHEA_DIR / "output"
PROPERTIES_PATH = SYNTHEA_DIR / "synthea.properties"

# Export FHIR R4 transaction bundles only (one per patient, upsert-ready) —
# skip CSV/CCDA/bulk/text exports we don't use, to keep runs fast. Practitioner
# and hospital (Organization) export must stay ON: each patient's Encounters
# reference them via conditional-update (PUT-by-identifier) entries, and those
# references only resolve if the referenced Practitioner/Organization resource
# is actually included -- with it off, HAPI rejects the transaction as an
# unresolvable match URL.
PROPERTIES_CONTENT = """\
exporter.fhir.export = true
exporter.fhir.transaction_bundle = true
exporter.fhir.bulk_data = false
exporter.hospital.fhir.export = true
exporter.practitioner.fhir.export = true
exporter.ccda.export = false
exporter.csv.export = false
exporter.text.export = false
exporter.html.export = false
generate.append_numbers_to_person_names = false
"""


def ensure_jar() -> Path:
    SYNTHEA_DIR.mkdir(parents=True, exist_ok=True)
    if JAR_PATH.exists():
        return JAR_PATH
    print(f"Downloading Synthea ({JAR_URL}) -> {JAR_PATH} ...", file=sys.stderr)
    import httpx

    with httpx.stream("GET", JAR_URL, timeout=None, follow_redirects=True) as resp:
        resp.raise_for_status()
        tmp = JAR_PATH.with_suffix(".jar.part")
        with open(tmp, "wb") as f:
            f.writelines(resp.iter_bytes(chunk_size=1024 * 1024))
        tmp.rename(JAR_PATH)
    return JAR_PATH


def run_synthea(
    count: int,
    state: str = "Massachusetts",
    seed: int | None = None,
    max_age: int = 75,
) -> Path:
    """Run Synthea, writing per-patient FHIR bundles under OUTPUT_DIR/fhir.

    `max_age` caps the population's age range (default 0-75): a full 0-140
    range includes centenarian patients with decades of Claims/ExplanationOfBenefit
    history, producing multi-megabyte single-patient bundles that are slow to
    post and unnecessary for this demo -- capping keeps bundle sizes practical.

    Returns the directory containing the generated *.json bundle files.
    """
    if shutil.which("java") is None:
        raise RuntimeError("java is required to run Synthea but was not found on PATH")

    jar = ensure_jar()
    PROPERTIES_PATH.write_text(PROPERTIES_CONTENT, encoding="utf-8")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "java", "-jar", str(jar),
        "-p", str(count),
        "-a", f"0-{max_age}",
        "-c", str(PROPERTIES_PATH),
        "--exporter.baseDirectory", str(OUTPUT_DIR),
    ]
    if seed is not None:
        cmd += ["-s", str(seed)]
    cmd += [state]

    print(f"Running Synthea: {' '.join(cmd)}", file=sys.stderr)
    subprocess.run(cmd, cwd=SYNTHEA_DIR, check=True)

    fhir_dir = OUTPUT_DIR / "fhir"
    if not fhir_dir.exists():
        raise RuntimeError(f"Synthea run finished but {fhir_dir} was not created")
    return fhir_dir


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--state", default="Massachusetts")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max-age", type=int, default=75)
    args = parser.parse_args()
    out = run_synthea(args.count, args.state, args.seed, args.max_age)
    print(f"Generated patient bundles in: {out}")
