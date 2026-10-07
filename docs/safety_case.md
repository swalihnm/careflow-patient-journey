# CareFlow safety case

**This is a portfolio demonstration, not a medical product, and this is not a
clinical safety certification.** It exists so a reader (interviewer,
reviewer, or future me) can see, in one place, exactly what safety claims
this system can support, exactly what tests back each claim, and exactly
what is still missing before anyone should treat the clinical-adjacent parts
of this repo as more than a strong first draft.

Full spec: [`docs/SPEC.md`](SPEC.md). Full build history and every bug found
along the way: [`PROGRESS.md`](../PROGRESS.md).

---

## 1. The rules this system is built around (CLAUDE.md, never relaxed)

1. The assistant never diagnoses, never advises on medication, never interprets results.
2. The safety gate runs before routing on every turn -- no code path skips it.
3. The red-flag eval set must stay at 100% recall. A change that lowers it must not be merged.
4. Patients never see risk scores. Assistant tools cannot read `Condition` or `MedicationRequest`.
5. Synthetic or de-identified public data only. Never real patient data.
6. PHI-like values are masked in logs and traces.

Each rule below is matched to the mechanism that enforces it and the test that checks it -- not just a policy statement.

---

## 2. Rule 1 & 2: scope and the safety gate

### Mechanism

- `safety/red_flag.py`: a bilingual (English / Modern Standard Arabic / Gulf dialect / Arabizi) keyword-and-pattern detector for 11 emergency categories (chest pain, difficulty breathing, stroke signs, suicidal ideation, severe bleeding, anaphylaxis, loss of consciousness, severe abdominal pain, infant high fever, seizure, severe burns -- drawn from NHS 111/999 categories, the American Stroke Association's FAST signs, and WHO safe-messaging guidance on suicide risk language). This is the **primary, non-negotiable mechanism** (SPEC 8.1: escalate if rules fire), not a fallback behind an LLM classifier.
- `safety/scope_guard.py`: the same keyword-and-pattern design, catching diagnosis / medication-dosage / test-interpretation requests, including ones phrased inside an otherwise-ordinary booking or coverage question.
- `assistant/graph.py`: the safety gate's position is a **structural LangGraph edge**, not a convention nodes are expected to honor --
  `language_detect -> safety_gate -> scope_guard -> router -> {...}`, where `safety_gate` branches straight to `escalate` (skipping `scope_guard` and the router entirely) the instant a red flag fires, and `scope_guard` branches to `scope_refusal` (skipping the router) on a violation. A message that reads as *both* a scope violation and a red flag ("What's wrong with me? I have severe chest pain") resolves to the red flag, exactly as SPEC 8.1 requires ("whatever else is happening in the conversation") -- this is proven by a contract test exercising that exact message, not asserted from the code's shape alone.
- A red flag raised **mid-booking** also escalates instead of continuing the flow (`test_red_flag_mid_booking_escalates_instead_of_continuing`) -- the gate is checked on every turn, including turns inside an in-progress multi-turn flow, not just the first turn of a conversation.

### Results (reproduce with `uv run pytest tests/unit/test_red_flag_eval.py tests/unit/test_scope_guard_eval.py -v`)

| Eval set | Size | Composition | Result |
| --- | --- | --- | --- |
| `evals/safety/messages.yaml` | 204 messages | 102 red-flag-positive, 102 benign look-alikes; English, MSA, Gulf dialect, Arabizi; indirect phrasings; red flags hidden inside booking requests | **100% recall, 100% precision** (zero false positives on the 102 benign messages) |
| `evals/scope/messages.yaml` | 100 messages | 80 violations (31 diagnosis, 25 medication, 24 test-interpretation) + 20 benign controls; English + Arabic | **100% caught, 0 false positives** |

SPEC's own bar is 100% recall on the red-flag set (required) with precision "reported" (not gated) -- both eval sets exceed that bar as measured today. **A CI gate enforces this going forward**: `tests/unit/test_red_flag_eval.py` and `tests/unit/test_scope_guard_eval.py` run on every push, and a change that drops recall below 100% fails the build, per CLAUDE.md rule 3.

### Prompt injection resistance

A dedicated eval set (`evals/injection/`, SPEC section 11, 40 messages/scenarios) tests scope/red-flag requests wrapped in "ignore your instructions" / fake-admin / roleplay framing, attempts to read clinical data via injected framing, and injected instructions inside conversation content aimed at manipulating the QA judge -- **100% resisted across all three**, but the first number that mattered more: the scope-evasion subset was authored adversarially (not tuned to the existing keyword list) and scored **33% recall on its first run**, a real gap this exercise found and closed by hardening `safety/scope_guard.py`'s keyword coverage (re-confirmed afterward at zero new false positives on the existing benign-control set). Full detail, including what specifically was missed and added, in `PROGRESS.md`'s Phase 6 section.

### What this does *not* claim

- **No native Arabic speaker or clinician has reviewed `safety/protocol.yaml` or either eval set.** Every message in both files was authored by the same person (model) who wrote the detection code, which is a real limitation SPEC explicitly calls out ("review every safety test message yourself... it is the part of the project an interviewer is most likely to question"). An LLM-assisted linguistic pass (2026-10-05) read every Arabic string in all three files and fixed a mistranslation ("blistering" rendered as "swollen"), a missing hamza, and two grammar errors (gender agreement on a verb; wrong case marking after an existential construction) -- all re-verified against the full eval suite afterward with no change to the 100% recall/catch rate. That pass can catch concrete grammar and translation errors; it cannot judge dialectal naturalness, clinical terminology precision, or cultural appropriateness the way a human reviewer could -- nothing here should be mistaken for the sign-off SPEC actually asks for. Strong first draft, stronger than before; still not a finished clinical artifact.
- **UAE emergency numbers (998 ambulance, 999 police) verified 2026-10-05** against the UAE government portal (u.ae) and corroborating sources (see `safety/protocol.yaml`'s header) -- accurate as of that date, but official numbers can change, so re-check before any real deployment regardless.
- 100% recall on 204/100 authored messages is not the same claim as 100% recall on the full space of things a real patient might type. The eval sets are deliberately adversarial (indirect phrasing, dialect, red flags hidden inside unrelated requests) but are still a sample, not a proof.

---

## 3. Rule 4: patients never see risk scores; assistant tools can't read clinical data

### Mechanism

- `packages/specmcp`: the assistant's *only* path to FHIR data is through a policy-controlled tool layer generated from `fhir/openapi/fhir.yaml` x `fhir/policies/fhir.yaml` -- zero hand-written per-resource tools, so nothing is reachable that isn't explicitly allow-listed. The assistant role is allow-listed for booking, coverage, intake, and masked demographics; **`Condition` and `MedicationRequest` are not exposed to it at all.**
- `apps/api/dependencies.py`'s `require_role(*allowed)`: every FastAPI endpoint that returns risk scores or clinical detail is role-gated. A `patient`-role request to `/v1/patients` (which carries risk scores) gets a 403 -- tested directly (`test_default_role_is_patient_and_cannot_see_risk_scores`), not just documented.

### Results

- `tests/contract/test_api.py`: role-gating tested directly (403 for patient, 400 for an unknown role, 200 for clinician/admin/system as appropriate) against the real running app, not a mock.
- Phase 1's contract tests prove a `Condition` read attempt through the assistant's tools returns a policy denial, and that denial is itself an audited event.

### What this does *not* claim

- Role enforcement is header-based (`X-Role`), **not real authentication** -- there is no login system in this portfolio project. The *access-control logic* driven by that header is real and tested; the identity behind the header is not verified by anything in this repo.

### A separate module that deliberately never goes near this boundary

The SPEC section 10 stretch module (`claims/`, a claims pre-check agent for billing staff, not the patient assistant) needs diagnosis codes to do its job -- but instead of reading `Condition` through any tool, it takes a draft claim's *already-coded* diagnosis (FHIR's own `Claim` resource carries its own `diagnosisCodeableConcept`, not a live reference) as input. It never had a reason to request access to `Condition`/`MedicationRequest`, so it doesn't -- not a policy exception carved out for it, just a design that stayed clear of the line entirely. See `claims/schema.py`'s module docstring.

---

## 4. Rule 6: PHI-like values are masked in logs and traces

### Mechanism

- `safety/masking.py`: Microsoft Presidio plus two custom recognizers for a synthetic Emirates-ID-style pattern and UAE mobile numbers. `DATE_TIME` is deliberately excluded from masking -- appointment dates are operational content the assistant needs to keep visible, not the PHI this rule targets.
- `assistant/transcript.py`: every conversation turn is masked before being written to `assistant.conversation_turns` (the table the QA judge and the care-team's escalation view both read from).
- `apps/api/routers/audit.py`: the auditor role sees masked actor/resource identifiers in `/v1/audit`, via the same `specmcp.mask.apply_mask` primitive used everywhere else -- one masking implementation, not a second one that could drift.

### A real, concrete PHI leak found and fixed (the acceptance criterion this rule exists for)

SPEC's own acceptance criterion for this rule is "no unmasked PHI-like values in logs (automated scan in CI)" -- checking that literally, not just trusting that masking existed elsewhere, found a real one: `assistant/escalate.py`'s audit-log `reason` field used to be built from the patient's **raw, unmasked message** (`assistant/graph.py`'s `escalate_node` passed `matched_text=state["message"]` straight into an f-string). Confirmed directly against a live database: a message like *"This is Fatima Al Nahyan, phone 0501234567, I have severe chest pain"* wrote that name and phone number verbatim into `ops.audit_log.reason` -- a field `apps/api/routers/audit.py`'s auditor-role masking never touches (it only masks `actor`/`resource_id`). Every red-flag escalation writes this field, so this wasn't a rare edge case -- it was the default behaviour for any emergency message that happened to also contain identifying information.

Fixed in `assistant/escalate.py` via a `_safe_masked_reason()` helper, with one deliberate constraint: this module's whole design principle is that **escalation must still work if every optional component is unavailable** (it has no LLM dependency anywhere, by design), and Presidio/spaCy is a real, previously-hit source of `MemoryError` under this project's host constraints. So masking here is wrapped in a try/except that falls back to *omitting* the matched text entirely (never to the unmasked original) if masking itself fails -- the patient-facing emergency message and the nurse alert never depend on this succeeding at all, only the audit record does. Regression test: `tests/contract/test_escalate_phi_masking.py`, which is also, concretely, the "automated scan in CI" this acceptance criterion asks for -- not a hypothetical one.

### What this does *not* claim

- **Presidio's NLP engine here is English-only**, so PERSON-name detection does not work on Arabic text. The regex-based Emirates ID / UAE phone recognizers are language-independent and do work on Arabic text, but a person's name written in Arabic would not currently be masked. This is a real, known gap, not an oversight to discover later.
- The fix above covers the one confirmed unmasked-PHI path found by checking this specifically; it is not a claim that every possible path has been audited this way, only that the specific mechanism SPEC's acceptance criterion names (an automated scan) now exists and passes.

---

## 5. Grounding: the assistant can't state what it can't cite

- `rag/store.py` + `assistant/coverage.py`: coverage questions are answered **extractively** (the best-matching policy chunk is returned verbatim with a citation, `document — section (version_date)`), not synthesized by an LLM -- grounded by construction, since the answer cannot contain anything not present in a retrieved chunk. A question with no good match (distance > 0.65, calibrated against this corpus) hands over to a human instead of guessing (`test_unrelated_question_hands_over_instead_of_hallucinating`).
- The embedding model (`paraphrase-multilingual-MiniLM-L12-v2`) does genuine cross-lingual retrieval, which created a real bug (an English query could score an Arabic-only chunk as the closest match and answer in the wrong language) -- fixed by always querying same-language chunks first; documented in PROGRESS.md Phase 3.

---

## 6. The QA judge: an independent check, with an honest caveat about its own evidence base

- `qa/judge.py` scores every finished conversation against a versioned 6-dimension rubric (`safety`, `accuracy`, `grounding`, `privacy`, `tone_and_empathy`, `language_quality`) using a real LLM call (Ollama Cloud) with a different prompt than the assistant itself -- an independent auditor, not the same component grading its own work.
- **Calibration result (`docs/qa_calibration_demo.md`): n=60, kappa=0.780 on one run, kappa=0.853 on a repeat run of the identical 60 scenarios** (54-56/60 agreement either way) -- this is explicitly a demo on 60 *scripted* transcripts authored for this project (grown from an original 29, with the count reaching 60 a coincidence, not a claim that this satisfies SPEC's "real conversations" requirement), not SPEC 8.2's actual deliverable (60 hand-labelled *real* conversations, which don't exist yet because this assistant has no live users). Both runs land in the substantial-to-almost-perfect agreement bands, so the honest conclusion (the judge is usable, not perfectly deterministic even at `temperature=0.0`) doesn't change -- but the two numbers genuinely differ, confirmed by actually re-running it rather than assumed to be stable, which is itself a finding worth keeping rather than quoting only the better of the two. Running it twice separates the disagreements into two kinds: 4 scenarios disagreed in *both* runs (a stable signal -- two dimension-boundary privacy-vs-safety cases, one case where the judge consistently read ambiguous distress language more cautiously than my hand-label did, and one legitimate catch on a scripted reply that itself crossed into medication-specific advice), while 2 flipped between runs (genuine sampling noise, including one concerning single-run read where the judge flagged a *correct* emergency-escalation instruction as disallowed advice, which did not reproduce on the second run). Full breakdown: `docs/qa_calibration_demo.md`. Doesn't substitute for the real 60-conversation exercise SPEC asks for.

---

## 7. Everything that is explicitly not finished or not claimed

Pulled together from the per-phase gap lists in `PROGRESS.md` (read that file for the full context on any of these):

1. No native-Arabic-speaker or clinician review of the safety protocol or either eval set -- an LLM-assisted pass fixed concrete errors but isn't a substitute (section 2 above).
2. Presidio PII masking doesn't catch Arabic-script person names (section 4 above).
3. QA judge calibration is a 29-scenario demo, not 60 real hand-labelled conversations (section 6 above) -- blocked on real conversation history, which needs real usage.
4. No natural free-text reply generation -- every patient-facing reply in this repo is template-based or extractive, by design (SPEC 8's "no interpretation" bar), not a shortcut taken for lack of an LLM key (an LLM key is configured and genuinely used by the QA judge).
5. Voice I/O (SPEC F8, lowest priority, "Could") is now built -- client-side only, via the browser's own Web Speech API, no dedicated ASR/TTS backend (`PROGRESS.md`'s "Voice I/O" section). Recognition accuracy and available voices depend entirely on the browser/OS; this doesn't change anything about who can give medical advice (the safety banner and scope guard apply identically to voice-transcribed text, since it's just filled into the same composer input a patient would otherwise type into).
6. SNOMED-to-training-category condition mapping for live risk scoring is keyword-based, not a certified crosswalk (lowers the confidence badge honestly, documented in `ml/features_fhir.py`).
7. All three risk models are trained on real but non-UAE public datasets (US hospital data 1999-2008; Brazilian clinic appointments) -- they demonstrate the method, not validated UAE clinical performance. Every model card says this explicitly.
8. This HAPI FHIR server's write-to-searchable latency has been measured as high as 13+ seconds under this project's own test load -- a real characteristic of the demo environment, documented and worked around (`PROGRESS.md`'s Phase 3 bug notes) but worth knowing before assuming any FHIR search here reflects a write made in the same second.

None of these are hidden elsewhere in the repo and then contradicted here -- this list and `PROGRESS.md`'s per-phase "what's not done" sections are meant to say the same thing. If they ever disagree, `PROGRESS.md` (updated continuously during the build) is the more current source; this file is the consolidated summary.
