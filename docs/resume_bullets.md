# Resume bullets (SPEC section 15)

SPEC's own template, every `[X]` filled with a real measured value from this
build (see `PROGRESS.md` and `docs/safety_case.md` for how each number was
produced). No `[live demo]` link -- this is a local-only portfolio project
with no cloud deployment target (see README's own framing); link to the
GitHub repo and, if useful, to specific files (model cards, the safety
case, the conversation/injection eval reports) instead.

---

**CareFlow: Patient Journey Intelligence Platform** · Python, HAPI FHIR, LangGraph, MCP, LightGBM, SHAP, Fairlearn, FastAPI, Next.js (EN/AR) · [GitHub]

- Built a bilingual (English/Arabic) patient assistant over a FHIR R4 record that books appointments, answers coverage questions with citations and runs structured intake, with a two-stage red-flag safety layer reaching 100% recall on a 204-message test set (and a separate 40-message/scenario prompt-injection eval, also 100% resisted).
- Trained calibrated readmission, length-of-stay and no-show models on 101,766 de-identified hospital encounters and 110,527 real appointment records (readmission AUROC 0.671, AUPRC 0.226; no-show AUROC 0.738, AUPRC 0.369) with SHAP drivers, subgroup fairness analysis and model cards, served live as FHIR RiskAssessment resources via a role-gated FastAPI backend.
- Designed an LLM QA judge scoring every conversation for safety, grounding and privacy, validated against 60 hand-labelled scripted conversations (Cohen's kappa 0.780 and 0.853 across two independent runs -- not yet the full 60-*real*-conversation calibration SPEC specifies, honestly labelled as a demo pending real usage data).
- Ran a pre-registered reminder A/B experiment with power analysis, estimating a 5.0-point absolute no-show reduction (95% CI [-6.8%, -3.2%], p = 8.4e-8) from a two-step SMS reminder vs. a single message.
- Shipped two live-verified Next.js front ends (a care-team dashboard and a bilingual patient chat app, with browser-native voice I/O) and a 120-scenario conversation eval suite (100% task success, 100% grounding) plus a 7-scenario Playwright E2E suite covering SPEC's named acceptance criteria, all gating CI alongside a nightly eval-run pipeline.

---

### Honesty notes on these numbers (don't drop these if reusing this elsewhere)

- The QA judge calibration is **60 scripted transcripts I authored and hand-labelled myself** (the count matching SPEC's own number is a coincidence, grown from an original 29), not SPEC's actual ask of 60 *real* conversations -- there are no live users yet to generate real ones. Say "scripted calibration demo" if asked, not just "calibration."
- The reminder A/B result is a **simulation**: real patients, scored by the real trained model, but the *outcome* (did they actually show up) is simulated from an assumed effect size, not observed. SPEC itself asks for this to be labelled as such.
- All three risk models are trained on real, public, non-UAE datasets (US hospital data 1999-2008; Brazilian clinic appointments) -- they demonstrate the method, not validated UAE clinical performance.
