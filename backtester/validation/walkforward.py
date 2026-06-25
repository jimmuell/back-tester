"""
Rolling-window walk-forward stability analysis.

IMPORTANT FRAMING (ADR-013): This is a temporal-stability / consistency check,
not walk-forward optimization. Each window is a contiguous time segment of the
trade list; we report whether the strategy's core metrics are stable across
windows — not whether IS-optimised parameters generalise to OOS.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from backtester.ingest.models import Trade
from backtester.metrics.core import compute_metrics


@dataclass(frozen=True)
class Window:
    index: int
    start_time: datetime
    end_time: datetime
    n_trades: int
    expectancy: float
    profit_factor: float
    win_rate: float
    net_profit: float
    max_drawdown: float


@dataclass(frozen=True)
class WalkForwardResult:
    n_windows: int
    scheme: str                    # "rolling" — disjoint consecutive segments
    windows: list[Window]
    pct_windows_positive: float    # fraction with expectancy > 0
    expectancy_mean: float
    expectancy_std: float          # lower = more consistent across windows


def walk_forward(trades: list[Trade], *, n_windows: int = 5) -> WalkForwardResult:
    """
    Split trades into n_windows contiguous equal-count segments (by exit_time).

    Reports per-window core metrics and stability summary. Use this to check
    whether the strategy's behaviour is consistent across time — a monotonically
    declining expectancy across windows is a temporal-decay signal.

    This is NOT walk-forward optimization (ADR-013).
    """
    if not trades:
        raise ValueError("trades list is empty — cannot walk-forward")
    if n_windows < 2:
        raise ValueError(f"n_windows must be >= 2, got {n_windows}")
    if n_windows > len(trades):
        raise ValueError(
            f"n_windows ({n_windows}) > number of trades ({len(trades)}); "
            "each window must have at least one trade"
        )

    sorted_trades = sorted(trades, key=lambda t: t.exit_time)
    n = len(sorted_trades)

    # Build disjoint windows of as-equal-as-possible trade counts.
    # Extra trades (n % n_windows) are distributed one each to the first windows.
    base_size = n // n_windows
    remainder = n % n_windows

    windows: list[Window] = []
    start = 0
    for i in range(n_windows):
        size = base_size + (1 if i < remainder else 0)
        segment = sorted_trades[start : start + size]
        m = compute_metrics(segment)
        windows.append(Window(
            index=i,
            start_time=segment[0].exit_time,
            end_time=segment[-1].exit_time,
            n_trades=len(segment),
            expectancy=m.expectancy,
            profit_factor=m.profit_factor,
            win_rate=m.win_rate,
            net_profit=m.net_profit,
            max_drawdown=m.max_drawdown,
        ))
        start += size

    expectancies = [w.expectancy for w in windows]
    pct_positive = sum(1 for e in expectancies if e > 0) / n_windows
    exp_mean = float(np.mean(expectancies))
    exp_std = float(np.std(expectancies, ddof=0))

    return WalkForwardResult(
        n_windows=n_windows,
        scheme="rolling",
        windows=windows,
        pct_windows_positive=pct_positive,
        expectancy_mean=exp_mean,
        expectancy_std=exp_std,
    )
