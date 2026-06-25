#!/usr/bin/env python3
"""Demo: unified validate() orchestrator (TASK 009)."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from engine import ValidationConfig, ValidationResult, validate
from engine.ingest.models import Trade
from engine.ingest.synthetic import generate_bars
from engine.instruments import MES
from engine.report.html import write_full_report

APP_NAME = os.getenv("APP_NAME", "BackTester")

# ── Synthetic bars (trending) ─────────────────────────────────────────────────
bars = generate_bars(n_bars=300, seed=42, drift=0.003, daily_vol=0.008)
closes = bars.df["close"].to_numpy()
timestamps = bars.df.index
last_bar = len(closes) - 1

# ── Bar-consistent trades: 60 trades, hold=5 bars ────────────────────────────
rng = np.random.default_rng(99)
N, HOLD = 60, 5
entry_idxs = rng.integers(0, last_bar - HOLD, size=N)
is_long = rng.random(size=N) < 0.6  # slight long bias

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

# ── Run full validation ───────────────────────────────────────────────────────
config = ValidationConfig(
    mc_iterations=5_000,       # faster for demo
    random_entry_iterations=5_000,
    n_windows=5,
)
result: ValidationResult = validate(trades, bars, config=config)

# ── Console summary ───────────────────────────────────────────────────────────
m = result.metrics
print(f"\n{APP_NAME} — Validation Summary")
print("═" * 52)
print(f"  Trades        : {m.total_trades}")
print(f"  Net Profit    : ${m.net_profit:>10,.2f}")
print(f"  Expectancy    : ${m.expectancy:>10,.2f}")
print(f"  Win Rate      : {m.win_rate:.1%}")
print(f"  Max Drawdown  : ${m.max_drawdown:>10,.2f}")
print(f"  Profit Factor : {m.profit_factor:.2f}")

print("\n  Monte Carlo (bootstrap 95% CI):")
bs = result.bootstrap
exp_lo, exp_hi = bs.expectancy_ci
net_lo, net_hi = bs.net_profit_ci
print(f"    Expectancy   : ${bs.expectancy_point:,.2f}  CI [{exp_lo:,.2f} — {exp_hi:,.2f}]")
print(f"    Net Profit   : ${bs.net_profit_point:,.2f}  CI [{net_lo:,.2f} — {net_hi:,.2f}]")

print("\n  Shuffle risk of ruin     :", f"{result.shuffle.risk_of_ruin:.1%}")

if result.split:
    sp = result.split
    arrow = "✓" if not sp.edge_decayed else "✗ DECAYED"
    print(f"\n  IS/OOS split ({sp.oos_fraction:.0%} OOS)   : {arrow}")
    print(f"    IS expectancy : ${sp.in_sample.expectancy:,.2f}")
    print(f"    OOS expectancy: ${sp.out_sample.expectancy:,.2f}")

if result.walk_forward:
    wf = result.walk_forward
    print(f"\n  Walk-forward ({wf.n_windows} windows)   : {wf.pct_windows_positive:.0%} positive")

if result.buy_hold:
    bh = result.buy_hold
    verdict = "✓ beats" if bh.beats_buy_hold else "✗ trails"
    print(f"\n  Buy-and-hold baseline    : {verdict}")
    print(f"    Strategy net  : ${bh.strategy_net:,.2f}")
    print(f"    B&H net       : ${bh.buy_hold_net:,.2f}")

if result.random_entry:
    re = result.random_entry
    verdict = "✓ beats random" if re.beats_random else "✗ no signal vs exposure"
    print(f"\n  Random-entry benchmark   : {verdict}")
    print(f"    Percentile rank : {re.net_percentile_rank:.1%}")

if result.regimes:
    print("\n  Regime breakdowns:")
    for scheme, rb in result.regimes.items():
        counts = rb.trade_counts
        print(f"    [{scheme}] " + ", ".join(f"{k}:{v}" for k, v in counts.items()))

if result.skipped:
    print("\n  Skipped:")
    for s in result.skipped:
        print(f"    — {s}")

# ── Write HTML report ─────────────────────────────────────────────────────────
out = Path("reports/demo_validate.html")
write_full_report(
    result,
    out,
    meta={
        "Symbol": "ES (synthetic)",
        "Drift": "+0.003/bar",
        "Bars": str(len(bars.df)),
        "Trades": str(len(trades)),
        "MC iterations": str(config.mc_iterations),
    },
)
print(f"\nReport written → {out}")
