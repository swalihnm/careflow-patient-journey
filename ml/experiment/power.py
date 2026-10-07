"""Power analysis for the reminder A/B experiment (SPEC 6.4): sample size
needed to detect a 3-point absolute reduction in no-show rate at 80% power,
computed *before* the simulation runs -- not fit to whatever the simulated
data happened to produce.
"""

from dataclasses import dataclass

from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize


@dataclass(frozen=True)
class PowerResult:
    baseline_rate: float
    target_rate: float
    absolute_reduction: float
    alpha: float
    power: float
    required_n_per_arm: int


def required_sample_size(
    baseline_rate: float,
    absolute_reduction: float = 0.03,
    alpha: float = 0.05,
    power: float = 0.80,
) -> PowerResult:
    target_rate = baseline_rate - absolute_reduction
    effect_size = proportion_effectsize(baseline_rate, target_rate)

    analysis = NormalIndPower()
    n_per_arm = analysis.solve_power(effect_size=abs(effect_size), alpha=alpha, power=power, ratio=1.0)

    return PowerResult(
        baseline_rate=baseline_rate,
        target_rate=target_rate,
        absolute_reduction=absolute_reduction,
        alpha=alpha,
        power=power,
        required_n_per_arm=int(n_per_arm) + 1,  # round up
    )


if __name__ == "__main__":
    # Baseline no-show rate among HIGH-RISK patients specifically (not the
    # whole population) -- see ml/experiment/simulate.py for how that subset
    # is defined; this default is illustrative until simulate.py supplies
    # the real observed high-risk baseline.
    result = required_sample_size(baseline_rate=0.35, absolute_reduction=0.03)
    print(result)
