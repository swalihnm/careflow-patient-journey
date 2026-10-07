"""Runs the full reminder A/B experiment pipeline (SPEC 6.4): power analysis,
simulation, two-proportion z-test, CUPED, segment breakdown, report.

Usage: uv run python -m ml.experiment.run
"""

from pathlib import Path

from ml.experiment.analyze import (
    cuped_adjust,
    segment_by_age_band,
    two_proportion_ztest,
    variance_reduction,
)
from ml.experiment.power import required_sample_size
from ml.experiment.report import write_report
from ml.experiment.simulate import ASSUMED_RELATIVE_REDUCTION, build_experiment_population

REPORT_PATH = Path(__file__).resolve().parents[2] / "docs" / "experiment_report.md"


def dataframe_to_markdown_table(df) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            cells.append(f"{v:.1%}" if c == "rate" else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    population = build_experiment_population()
    print(f"High-risk population: {len(population)} patients")

    baseline_rate = population.loc[population["arm"] == "A", "simulated_no_show"].mean()
    power = required_sample_size(baseline_rate=baseline_rate, absolute_reduction=0.03)
    print(power)

    ztest_raw = two_proportion_ztest(population, "simulated_no_show")
    print(ztest_raw)

    cuped_df = cuped_adjust(population, "simulated_no_show", "no_show_risk")
    var_reduction = variance_reduction(cuped_df)
    ztest_cuped_note = f"Raw variance: {population['simulated_no_show'].var():.4f}; CUPED-adjusted variance: {cuped_df['cuped_adjusted'].var():.4f}"
    print(f"CUPED variance reduction: {var_reduction:.1%}")

    guardrail_a = population.loc[population["arm"] == "A", "simulated_cancellation"].mean()
    guardrail_b = population.loc[population["arm"] == "B", "simulated_cancellation"].mean()

    segments = segment_by_age_band(population, age_col="Age", outcome_col="simulated_no_show")
    segment_md = dataframe_to_markdown_table(segments)

    write_report(
        REPORT_PATH,
        power=power,
        ztest_raw=ztest_raw,
        ztest_cuped_note=ztest_cuped_note,
        variance_reduction_pct=var_reduction,
        segment_table_md=segment_md,
        assumed_relative_reduction=ASSUMED_RELATIVE_REDUCTION,
        guardrail_rate_a=guardrail_a,
        guardrail_rate_b=guardrail_b,
    )
    print(f"Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
