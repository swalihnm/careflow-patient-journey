# CareFlow

Full spec: docs/SPEC.md. Read the relevant section before any task.

Portfolio demonstration only — not a medical product. Synthetic/de-identified data only.

## Safety rules (never relax these)
- The assistant never diagnoses, never advises on medication, never interprets results.
- safety_gate runs before routing on every turn. Do not add any path that skips it.
- The red-flag eval set must stay at 100% recall. A change that lowers it must not be merged.
- Patients never see risk scores. Assistant tools cannot read Condition or MedicationRequest.
- Synthetic or de-identified public data only. Never add real patient data.
- PHI-like values are masked in logs and traces.

## Engineering rules
- One phase at a time (SPEC section 13). Plan first, wait for approval.
- All FHIR access goes through specmcp tools; all LLM calls through trustcore.gateway (once it exists — not yet built as of Phase 1).
- Patient-level train/test splits; leakage tests required for every model.
- Every user-facing string exists in English and Arabic.
- Tests with every feature; run `make test` before saying a task is done.
- `trustcore` and `specmcp` are local packages built fresh in this repo (packages/), not reused from elsewhere — see the implementation note at the end of docs/SPEC.md.

## Ports in use (avoid collisions with other local projects)
- Postgres: 5544
- HAPI FHIR: 8210
- HIE mock: 8211

## Commands
make setup | up | down | seed | seed-full | test | lint
