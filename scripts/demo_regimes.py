#!/usr/bin/env python3
"""Demo: regime tagging — trend and volatility breakdowns (TASK 008)."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from backtester.ingest.models import Trade
from backtester.ingest.synthetic import generate_bars
from backtester.instruments import MES
from backtester.metrics.core import compute_metrics
from backtester.report.html import write_report
from backtester.validation.regimes import classify_regimes, regime_breakdown

APP_NAME = os.getenv("APP_NAME", "BackTester")

# ── Build a trending bar set (positive drift) ─────────────────────────────────
bars = generate_bars(n_bars=300, seed=42, drift=0.003, daily_vol=0.008)
closes = bars.df["close"].to_numpy()
timestamps = bars.df.index
last_bar = len(closes) - 1

# ── Bar-consistent trades: random entries, 40 trades, hold=3 bars ─────────────
rng = np.random.default_rng(7)
N, HOLD = 40, 3
entry_idxs = rng.integers(0, last_bar, size=N)
is_long = rng.random(size=N) < 0.5
trades: list[Trade] = []
for tid, (ei, long) in enumerate(zip(entry_idxs.tolist(), is_long.tolist()), 1):
    ei = int(ei)
    xi = min(ei + HOLD, last_bar)
    direction = "long" if long else "short"
    dir_sign = 1 if long else -1
    pnl = dir_sign * (closes[xi] - closes[ei]) * MES.point_value
    trades.append(Trade(
        trade_id=tid, direction=direction,
        entry_time=timestamps[ei].to_pydatetime(),
        exit_time=timestamps[xi].to_pydatetime(),
        entry_price=float(closes[ei]),
        exit_price=float(closes[xi]),
        qty=1, pnl=pnl,
    ))

# ── Regime breakdowns ─────────────────────────────────────────────────────────
rb_trend = regime_breakdown(trades, bars, scheme="trend", ma_length=50.0)
rb_vol = regime_breakdown(trades, bars, scheme="volatility", vol_length=20.0)

# ── Print per-regime expectancy ───────────────────────────────────────────────
def _print_breakdown(title: str, rb: object) -> None:
    from backtester.validation.regimes import RegimeBreakdown
    rb_typed: RegimeBreakdown = rb  # type: ignore[assignment]
    print(f"\n{APP_NAME} — {title}")
    print("─" * 52)
    order = {"bull": 0, "range": 1, "bear": 2,
             "high_vol": 0, "low_vol": 1, "undefined": 99}
    for label, m in sorted(rb_typed.per_regime.items(), key=lambda kv: order.get(kv[0], 50)):
        sign = "✓" if m.expectancy >= 0 else "✗"
        print(
            f"  {label:<12} : {rb_typed.trade_counts[label]:>3} trades"
            f"  | expectancy ${m.expectancy:>8,.2f}"
            f"  | win rate {m.win_rate:.0%}"
            f"  {sign}"
        )

_print_breakdown("Trend Regime Breakdown (ma_length=50)", rb_trend)
_print_breakdown("Volatility Regime Breakdown (vol_length=20)", rb_vol)

# Quick sanity: label counts
trend_labels = classify_regimes(bars, scheme="trend", ma_length=50)
label_counts = trend_labels.value_counts()
print(f"\n  Bar label counts (trend): {dict(label_counts)}")

# ── Write report ──────────────────────────────────────────────────────────────
metrics = compute_metrics(trades)
out = Path("reports/demo_regimes.html")
write_report(
    metrics,
    out,
    regime=rb_trend,
    meta={
        "Symbol": "ES (synthetic)",
        "Drift": "+0.003/bar",
        "Bars": str(len(bars.df)),
        "Trades": str(len(trades)),
        "Scheme": "trend (ma_length=50)",
    },
)
print(f"\nReport written → {out}")
