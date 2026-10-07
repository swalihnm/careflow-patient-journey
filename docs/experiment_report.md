# Reminder A/B experiment report

Generated 2026-09-28

> **This is a simulation, not a live experiment.** Outcomes were simulated from the trained no-show model's predicted risk plus an assumed effect size (15% relative reduction for arm B), stated here explicitly (SPEC 6.4). The patient population and risk scores are real (from the no-show model's held-out test set); the outcomes are not.

## Question

Does a two-step reminder (SMS 3 days before + a second message on the day) reduce no-shows versus a single SMS, for high-risk patients?

## Design

High-risk appointments (top 30% by predicted no-show risk) randomised 50/50 to A (single SMS, control) or B (two-step reminder). Primary metric: no-show rate. Guardrail metric: cancellation rate.

## Power analysis (computed before simulating any outcomes)

- Baseline no-show rate among high-risk patients: 33.9%
- Target: detect a 3%-point absolute reduction (to 30.9%) at 80% power, alpha=0.05
- Required sample size: **3818 per arm** (7636 total)

## Primary metric: no-show rate

| Arm | n | No-show rate |
| --- | --- | --- |
| A (single SMS) | 5035 | 33.9% |
| B (two-step) | 4921 | 28.9% |

Absolute difference (B - A): **-5.0%** (95% CI [-6.8%, -3.2%])  
z = 5.359, p = 0.0000

**Decision: Ship B (two-step reminder): statistically significant reduction in no-show rate.**

## CUPED adjustment

Using the no-show model's pre-experiment predicted risk as the covariate (theta estimated pooled across arms, so it can't itself encode the treatment effect):

- Variance reduction from CUPED: **0.9%**
- Raw variance: 0.2155; CUPED-adjusted variance: 0.2135

## Guardrail metric: cancellation rate

| Arm | Cancellation rate |
| --- | --- |
| A | 5.1% |
| B | 5.0% |

No arm effect was assumed for cancellations in the simulation (see caveats) -- any difference shown here is simulation noise, not a modelled effect.

## Segment by age band

| age_band | arm | n | rate |
| --- | --- | --- | --- |
| 0-17 | A | 1619 | 34.6% |
| 0-17 | B | 1533 | 28.8% |
| 18-29 | A | 1318 | 32.9% |
| 18-29 | B | 1268 | 29.1% |
| 30-44 | A | 1330 | 33.7% |
| 30-44 | B | 1310 | 28.5% |
| 45-59 | A | 561 | 32.4% |
| 45-59 | B | 606 | 29.0% |
| 60-74 | A | 146 | 40.4% |
| 60-74 | B | 147 | 31.3% |
| 75+ | A | 61 | 37.7% |
| 75+ | B | 57 | 29.8% |

## Caveats

- **Simulated outcomes**, not observed data -- see the notice at the top of this report.
- The assumed effect size (15% relative reduction) is illustrative, not derived from any real reminder-effectiveness study for this population.
- The guardrail metric (cancellations) has no assumed treatment effect in the simulation; a real experiment would need to actually observe it, not simulate it.
- High-risk selection (top 30% by predicted risk) uses the same model whose test-set predictions are the covariate here -- in a live experiment, the model version used for targeting should be frozen and versioned before the experiment starts.
- CUPED's variance reduction here is small: for a binary/Bernoulli outcome, most of its variance is irreducible sampling noise (p(1-p)) rather than variance explained by the covariate, especially with the covariate confined to a fairly narrow risk band (the high-risk subset only). CUPED helps more on continuous outcomes with a wider-ranging covariate; this result is a realistic, not disappointing, demonstration of that limit.