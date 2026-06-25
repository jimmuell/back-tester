"""
Bootstrap Monte Carlo (resample WITH replacement).

Each iteration draws len(trades) trades with replacement, creating a new
synthetic sample. This varies the EDGE itself, not just the path — yielding
confidence intervals on expectancy, profit factor, net P&L, and win rate.

CIs use the percentile bootstrap (no bias-correction) which is appropriate for
trading metrics where the underlying distribution is unknown. For Sharpe-with-CI,
use the BCa bootstrap (deferred to the metrics slice).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.ingest.models import Trade

_SUPPORTED_CI_LEVELS = {0.90, 0.95, 0.99}


@dataclass(frozen=True)
class BootstrapResult:
    n_iterations: int
    seed: int
    ci_level: float
    expectancy_point: float
    expectancy_ci: tuple[float, float]
    net_profit_point: float
    net_profit_ci: tuple[float, float]
    profit_factor_point: float
    profit_factor_ci: tuple[float, float]
    win_rate_point: float
    win_rate_ci: tuple[float, float]
    n_inf_pf: int              # resamples where all trades were wins (PF = ∞)
    expectancy_dist: list[float]   # per-resample expectancy, for inspection / tests


def _resample_metrics(
    pnl_arr: np.ndarray,
    indices: np.ndarray,
) -> tuple[float, float, float, float]:
    """
    Return (expectancy, net_profit, profit_factor, win_rate) for a bootstrap resample.
    profit_factor is returned as np.inf when there are no losses; caller counts these.
    """
    sample = pnl_arr[indices]
    n = len(sample)
    wins = sample[sample > 0]
    losses = sample[sample <= 0]

    net = float(sample.sum())
    expectancy = net / n
    win_rate = len(wins) / n
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss_abs = float((-losses).sum()) if len(losses) else 0.0
    profit_factor = gross_profit / gross_loss_abs if gross_loss_abs > 0 else np.inf

    return expectancy, net, profit_factor, win_rate


def _percentile_ci(arr: np.ndarray, ci_level: float) -> tuple[float, float]:
    alpha = 1.0 - ci_level
    lo = float(np.percentile(arr, alpha / 2 * 100))
    hi = float(np.percentile(arr, (1 - alpha / 2) * 100))
    return lo, hi


def run_bootstrap(
    trades: list[Trade],
    *,
    n_iterations: int = 10_000,
    seed: int = 42,
    ci_level: float = 0.95,
) -> BootstrapResult:
    """
    Run bootstrap Monte Carlo (resample WITH replacement).

    Each iteration resamples len(trades) trades with replacement and recomputes
    core metrics. Percentile CIs reveal uncertainty in the edge itself.

    Infinite profit factors (no-loss resamples) are counted in n_inf_pf and
    excluded from the PF percentiles so they do not poison the CI calculation.
    """
    if not trades:
        raise ValueError("trades list is empty")
    if ci_level not in _SUPPORTED_CI_LEVELS:
        raise ValueError(f"ci_level must be one of {_SUPPORTED_CI_LEVELS}, got {ci_level}")

    rng = np.random.default_rng(seed)
    pnl_arr = np.array([t.pnl for t in trades], dtype=np.float64)
    n = len(pnl_arr)

    # Point estimates from the full sample
    full_wins = pnl_arr[pnl_arr > 0]
    full_losses = pnl_arr[pnl_arr <= 0]
    expectancy_point = float(pnl_arr.mean())
    net_profit_point = float(pnl_arr.sum())
    win_rate_point = float(len(full_wins) / n)
    gross_profit_pt = float(full_wins.sum()) if len(full_wins) else 0.0
    gross_loss_abs_pt = float((-full_losses).sum()) if len(full_losses) else 0.0
    pf_point = gross_profit_pt / gross_loss_abs_pt if gross_loss_abs_pt > 0 else np.inf

    # Bootstrap iterations — batch index generation for speed
    all_indices = rng.integers(0, n, size=(n_iterations, n))

    exp_dist: list[float] = []
    net_dist: list[float] = []
    pf_finite: list[float] = []
    wr_dist: list[float] = []
    n_inf_pf = 0

    for i in range(n_iterations):
        exp, net, pf, wr = _resample_metrics(pnl_arr, all_indices[i])
        exp_dist.append(exp)
        net_dist.append(net)
        wr_dist.append(wr)
        if np.isinf(pf):
            n_inf_pf += 1
        else:
            pf_finite.append(pf)

    exp_arr = np.array(exp_dist)
    net_arr = np.array(net_dist)
    wr_arr = np.array(wr_dist)
    pf_arr = np.array(pf_finite) if pf_finite else np.array([0.0])

    return BootstrapResult(
        n_iterations=n_iterations,
        seed=seed,
        ci_level=ci_level,
        expectancy_point=expectancy_point,
        expectancy_ci=_percentile_ci(exp_arr, ci_level),
        net_profit_point=net_profit_point,
        net_profit_ci=_percentile_ci(net_arr, ci_level),
        profit_factor_point=float(pf_point),
        profit_factor_ci=_percentile_ci(pf_arr, ci_level),
        win_rate_point=win_rate_point,
        win_rate_ci=_percentile_ci(wr_arr, ci_level),
        n_inf_pf=n_inf_pf,
        expectancy_dist=exp_dist,
    )
