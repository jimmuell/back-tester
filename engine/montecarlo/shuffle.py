"""
Trade-order shuffle Monte Carlo (resample WITHOUT replacement).

Each iteration keeps the SAME set of trades but randomizes their ORDER.
Net P&L is therefore INVARIANT — it equals sum(pnl) on every path.
What varies is path-dependent statistics: max drawdown, losing streaks,
time-under-water, and risk of experiencing a given drawdown level.

The `risk_of_ruin` field answers: "what fraction of possible trade orderings
produce a max drawdown >= ruin_threshold?"  This is NOT a true account-ruin
probability — that requires an account size. It is a drawdown-exceedance
probability given the observed trade set.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.ingest.models import Trade
from engine.metrics.core import compute_metrics

_PCTILE_KEYS = (5, 25, 50, 75, 95)


@dataclass(frozen=True)
class ShuffleResult:
    n_iterations: int
    seed: int
    net_profit: float                        # invariant = sum(t.pnl for t in trades)
    max_drawdown_dist: list[float]           # one max-drawdown per shuffled path
    max_drawdown_pctiles: dict[int, float]   # keys 5,25,50,75,95
    longest_loss_streak_dist: list[int]      # one longest-loss-streak per path
    ruin_threshold: float                    # drawdown level tested
    risk_of_ruin: float                      # fraction of paths with max_dd >= threshold


def _max_drawdown_and_streak(pnl_seq: np.ndarray) -> tuple[float, int]:
    """Compute max drawdown (USD) and longest losing streak from a P&L sequence."""
    equity = np.cumsum(pnl_seq)
    peak = equity[0]
    max_dd = 0.0
    for eq in equity:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd

    cur_loss = 0
    longest = 0
    for p in pnl_seq:
        if p <= 0:
            cur_loss += 1
            if cur_loss > longest:
                longest = cur_loss
        else:
            cur_loss = 0
    return max_dd, longest


def run_shuffle(
    trades: list[Trade],
    *,
    n_iterations: int = 10_000,
    seed: int = 42,
    ruin_threshold: float | None = None,
) -> ShuffleResult:
    """
    Run trade-order shuffle Monte Carlo.

    Randomizes trade ORDER (not the trade set) across n_iterations paths.
    Net P&L is invariant. Max drawdown and losing-streak distributions reveal
    the range of outcomes the SAME edge can produce purely from ordering.

    ruin_threshold: USD drawdown level for risk_of_ruin.
        Defaults to the original-ordering observed max drawdown, so
        risk_of_ruin = P[a shuffled path's drawdown >= as-observed drawdown].
    """
    if not trades:
        raise ValueError("trades list is empty")

    rng = np.random.default_rng(seed)
    pnl_arr = np.array([t.pnl for t in trades], dtype=np.float64)
    net_profit = float(pnl_arr.sum())

    # Default ruin_threshold to observed max drawdown
    if ruin_threshold is None:
        original_metrics = compute_metrics(trades)
        ruin_threshold = original_metrics.max_drawdown

    dd_dist: list[float] = []
    streak_dist: list[int] = []

    for _ in range(n_iterations):
        shuffled = rng.permutation(pnl_arr)
        dd, streak = _max_drawdown_and_streak(shuffled)
        dd_dist.append(float(dd))
        streak_dist.append(int(streak))

    dd_arr = np.array(dd_dist)
    pctiles = {k: float(np.percentile(dd_arr, k)) for k in _PCTILE_KEYS}
    risk_of_ruin = float(np.mean(dd_arr >= ruin_threshold))

    return ShuffleResult(
        n_iterations=n_iterations,
        seed=seed,
        net_profit=net_profit,
        max_drawdown_dist=dd_dist,
        max_drawdown_pctiles=pctiles,
        longest_loss_streak_dist=streak_dist,
        ruin_threshold=ruin_threshold,
        risk_of_ruin=risk_of_ruin,
    )
