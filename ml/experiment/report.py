"""Renders the reminder A/B experiment report (SPEC 6.4 output: "Experiment
report page ... with the decision and caveats")."""

from datetime import UTC, datetime
from pathlib import Path

from ml.experiment.analyze import ZTestResult
from ml.experiment.power import PowerResult

DECISION_THRESHOLD_P = 0.05


def decide(ztest: ZTestResult) -> str:
    if ztest.p_value < DECISION_THRESHOLD_P and ztest.absolute_difference < 0:
        return "Ship B (two-step reminder): statistically significant reduction in no-show rate."
    if ztest.p_value < DECISION_THRESHOLD_P and ztest.absolute_difference > 0:
        return "Do not ship B: statistically significant *increase* in no-show rate."
    return "Inconclusive: difference is not statistically significant at alpha=0.05."


def render_report(
    *,
    power: PowerResult,
    ztest_raw: ZTestResult,
    ztest_cuped_note: str,
    variance_reduction_pct: float,
    segment_table_md: str,
    assumed_relative_reduction: float,
    guardrail_rate_a: float,
    guardrail_rate_b: float,
) -> str:
    lines = [
        "# Reminder A/B experiment report",
        "",
        f"Generated {datetime.now(UTC).date().isoformat()}",
        "",
        (
            "> **This is a simulation, not a live experiment.** Outcomes were simulated from the "
            "trained no-show model's predicted risk plus an assumed effect size "
            f"({assumed_relative_reduction:.0%} relative reduction for arm B), stated here explicitly "
            "(SPEC 6.4). The patient population and risk scores are real (from the no-show model's "
            "held-out test set); the outcomes are not."
        ),
        "",
        "## Question",
        "",
        (
            "Does a two-step reminder (SMS 3 days before + a second message on the day) reduce "
            "no-shows versus a single SMS, for high-risk patients?"
        ),
        "",
        "## Design",
        "",
        (
            "High-risk appointments (top 30% by predicted no-show risk) randomised 50/50 to A "
            "(single SMS, control) or B (two-step reminder). Primary metric: no-show rate. "
            "Guardrail metric: cancellation rate."
        ),
        "",
        "## Power analysis (computed before simulating any outcomes)",
        "",
        f"- Baseline no-show rate among high-risk patients: {power.baseline_rate:.1%}",
        (
            f"- Target: detect a {power.absolute_reduction:.0%}-point absolute reduction "
            f"(to {power.target_rate:.1%}) at {power.power:.0%} power, alpha={power.alpha}"
        ),
        (
            f"- Required sample size: **{power.required_n_per_arm} per arm** "
            f"({power.required_n_per_arm * 2} total)"
        ),
        "",
        "## Primary metric: no-show rate",
        "",
        "| Arm | n | No-show rate |",
        "| --- | --- | --- |",
        f"| A (single SMS) | {ztest_raw.n_a} | {ztest_raw.rate_a:.1%} |",
        f"| B (two-step) | {ztest_raw.n_b} | {ztest_raw.rate_b:.1%} |",
        "",
        (
            f"Absolute difference (B - A): **{ztest_raw.absolute_difference:+.1%}** "
            f"(95% CI [{ztest_raw.ci_low:+.1%}, {ztest_raw.ci_high:+.1%}])  "
        ),
        f"z = {ztest_raw.z_stat:.3f}, p = {ztest_raw.p_value:.4f}",
        "",
        f"**Decision: {decide(ztest_raw)}**",
        "",
        "## CUPED adjustment",
        "",
        (
            "Using the no-show model's pre-experiment predicted risk as the covariate (theta "
            "estimated pooled across arms, so it can't itself encode the treatment effect):"
        ),
        "",
        f"- Variance reduction from CUPED: **{variance_reduction_pct:.1%}**",
        f"- {ztest_cuped_note}",
        "",
        "## Guardrail metric: cancellation rate",
        "",
        "| Arm | Cancellation rate |",
        "| --- | --- |",
        f"| A | {guardrail_rate_a:.1%} |",
        f"| B | {guardrail_rate_b:.1%} |",
        "",
        (
            "No arm effect was assumed for cancellations in the simulation (see caveats) -- any "
            "difference shown here is simulation noise, not a modelled effect."
        ),
        "",
        "## Segment by age band",
        "",
        segment_table_md,
        "",
        "## Caveats",
        "",
        "- **Simulated outcomes**, not observed data -- see the notice at the top of this report.",
        (
            "- The assumed effect size (15% relative reduction) is illustrative, not derived from any "
            "real reminder-effectiveness study for this population."
        ),
        (
            "- The guardrail metric (cancellations) has no assumed treatment effect in the simulation; "
            "a real experiment would need to actually observe it, not simulate it."
        ),
        (
            "- High-risk selection (top 30% by predicted risk) uses the same model whose test-set "
            "predictions are the covariate here -- in a live experiment, the model version used for "
            "targeting should be frozen and versioned before the experiment starts."
        ),
        (
            "- CUPED's variance reduction here is small: for a binary/Bernoulli outcome, most of its "
            "variance is irreducible sampling noise (p(1-p)) rather than variance explained by the "
            "covariate, especially with the covariate confined to a fairly narrow risk band "
            "(the high-risk subset only). CUPED helps more on continuous outcomes with a wider-ranging "
            "covariate; this result is a realistic, not disappointing, demonstration of that limit."
        ),
    ]
    return "\n".join(lines)


def write_report(path: Path, **kwargs) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(**kwargs), encoding="utf-8")
