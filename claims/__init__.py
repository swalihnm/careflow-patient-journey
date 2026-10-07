"""SPEC section 10 stretch module: claims pre-check agent.

Reviews a draft claim built from a FHIR Encounter + Coverage and flags likely
rejection reasons before submission -- never changes the claim itself (every
flag is a suggestion for a human coder, see claims/store.py for how a coder's
decision is recorded and audited). Demonstration only, per SPEC's own honesty
note: no public labelled claims-denial dataset exists, so this is evaluated
against synthetic injected problems (evals/claims/), not real denial outcomes.

Staff/back-office tool, not the patient-facing bilingual assistant -- English
only, same precedent as apps/care-web's dashboard (which also has no i18n).
"""
