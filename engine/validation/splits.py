"""
Chronological in-sample / out-of-sample split.

IMPORTANT FRAMING (ADR-013): Because the MVP does not optimize strategy parameters
in-app (TradingView handles that in Slice 4), this is a TEMPORAL-STABILITY /
hold-out CONSISTENCY check — not classic optimize-IS / validate-OOS.

What it answers: "Given a single trade list, do early trades and late trades tell
the same story?"  A decaying edge (positive IS expectancy, non-positive OOS) is a
red flag worth flagging explicitly.  It does NOT confirm that the strategy was
developed on IS and validated on OOS.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from engine.ingest.models import Trade
from engine.metrics.core import Metrics, compute_metrics


@dataclass(frozen=True)
class SplitResult:
    oos_fraction: float
    split_index: int          # first index of the OOS segment (after time-sort)
    split_time: datetime      # exit_time of the last IS trade
    in_sample: Metrics
    out_sample: Metrics
    edge_decayed: bool        # IS expectancy > 0 AND OOS expectancy <= 0
    expectancy_ratio: float   # OOS expectancy / IS expectancy (guarded against div-by-zero)


def _safe_ratio(numerator: float, denominator: float) -> float:
    """OOS / IS expectancy ratio, guarded for zero and sign changes."""
    if denominator == 0.0:
        return float("nan")
    return numerator / denominator


def in_out_split(trades: list[Trade], *, oos_fraction: float = 0.30) -> SplitResult:
    """
    Split trades chronologically into in-sample and out-of-sample segments.

    Trades are sorted by exit_time. The first (1 - oos_fraction) of trades form
    the IS segment; the remainder form OOS.

    This is a temporal-stability check (ADR-013), not optimize-IS / validate-OOS.
    """
    if not trades:
        raise ValueError("trades list is empty — cannot split")
    if not (0.0 < oos_fraction < 1.0):
        raise ValueError(f"oos_fraction must be in (0, 1), got {oos_fraction}")

    sorted_trades = sorted(trades, key=lambda t: t.exit_time)
    n = len(sorted_trades)
    split_idx = max(1, round(n * (1.0 - oos_fraction)))

    if split_idx >= n:
        raise ValueError(
            f"oos_fraction={oos_fraction} leaves no OOS trades "
            f"(n={n}, split_idx={split_idx})"
        )

    is_trades = sorted_trades[:split_idx]
    oos_trades = sorted_trades[split_idx:]

    is_metrics = compute_metrics(is_trades)
    oos_metrics = compute_metrics(oos_trades)

    edge_decayed = is_metrics.expectancy > 0 and oos_metrics.expectancy <= 0
    ratio = _safe_ratio(oos_metrics.expectancy, is_metrics.expectancy)

    return SplitResult(
        oos_fraction=oos_fraction,
        split_index=split_idx,
        split_time=is_trades[-1].exit_time,
        in_sample=is_metrics,
        out_sample=oos_metrics,
        edge_decayed=edge_decayed,
        expectancy_ratio=ratio,
    )
