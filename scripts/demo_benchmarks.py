#!/usr/bin/env python3
"""Demo: synthetic bars + buy-and-hold + random-entry benchmarks (TASKs 006–007)."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import numpy as np

from engine.ingest.models import Trade
from engine.ingest.synthetic import generate_bars, generate_trades
from engine.instruments import MES
from engine.metrics.core import compute_metrics
from engine.report.html import write_report
from engine.validation.benchmarks import buy_and_hold, random_entry

APP_NAME = os.getenv("APP_NAME", "BackTester")

# ── Shared bars ───────────────────────────────────────────────────────────────
bars = generate_bars(timeframe="1day", n_bars=252, seed=42, start=date(2024, 1, 2))
closes = bars.df["close"].to_numpy()
timestamps = bars.df.index
last_bar = len(closes) - 1

# ── TASK 006: buy-and-hold (uses generate_trades — intraday times on daily bars is OK
#    for buy_and_hold since it only needs the date range, not bar-index alignment) ────
tv_trades = generate_trades(n_trades=100, profile="edge", seed=42, start_date=date(2024, 2, 1))
bh = buy_and_hold(tv_trades, bars, instrument=MES, qty=1)
metrics = compute_metrics(tv_trades)

print(f"\n{APP_NAME} — Buy-and-Hold Benchmark")
print("─" * 45)
print(f"  Strategy net profit : ${bh.strategy_net:,.2f}")
print(f"  Buy-and-hold net    : ${bh.buy_hold_net:,.2f}")
print(f"  Beats buy-and-hold  : {'✓ YES' if bh.beats_buy_hold else '✗ NO'}")
print(f"  Entry bar close     : {bh.start_price:,.2f}  ({bh.start_time.strftime('%Y-%m-%d')} UTC)")
print(f"  Exit bar close      : {bh.end_price:,.2f}  ({bh.end_time.strftime('%Y-%m-%d')} UTC)")

# ── TASK 007: random-entry — build bar-consistent trades for a fair comparison ───────
#    Entry/exit times are exactly bar timestamps → hold computed in bar-index space.
N_DEMO = 30
HOLD = 5

# EDGE: cherry-pick the N_DEMO entries with the largest |5-bar forward move|,
#       go long when the move is up, short when down → pnl is always positive.
fwd_moves = np.array([
    closes[min(i + HOLD, last_bar)] - closes[i] for i in range(last_bar)
])
top_idxs = np.argsort(np.abs(fwd_moves))[::-1][:N_DEMO]
edge_trades: list[Trade] = []
for tid, i in enumerate(top_idxs, 1):
    exit_i = min(i + HOLD, last_bar)
    move = closes[exit_i] - closes[i]
    direction = "long" if move >= 0 else "short"
    dir_sign = 1 if direction == "long" else -1
    edge_trades.append(Trade(
        trade_id=tid,
        direction=direction,
        entry_time=timestamps[i].to_pydatetime(),
        exit_time=timestamps[exit_i].to_pydatetime(),
        entry_price=float(closes[i]),
        exit_price=float(closes[exit_i]),
        qty=1,
        # dir_sign * move: long rides up (+*+ = +); short rides down (-*- = +)
        pnl=dir_sign * move * MES.point_value,
    ))

# NOISE: random entries with uniform direction — no signal, just exposure.
rng_noise = np.random.default_rng(7)
noise_entry_idxs = rng_noise.integers(0, last_bar, size=N_DEMO)
noise_is_long = rng_noise.random(size=N_DEMO) < 0.5
noise_trades: list[Trade] = []
for tid, (entry_i, is_long) in enumerate(zip(noise_entry_idxs.tolist(), noise_is_long.tolist()), 1):
    entry_i = int(entry_i)
    exit_i = min(entry_i + HOLD, last_bar)
    direction = "long" if is_long else "short"
    dir_sign = 1 if is_long else -1
    move = closes[exit_i] - closes[entry_i]
    noise_trades.append(Trade(
        trade_id=tid,
        direction=direction,
        entry_time=timestamps[entry_i].to_pydatetime(),
        exit_time=timestamps[exit_i].to_pydatetime(),
        entry_price=float(closes[entry_i]),
        exit_price=float(closes[exit_i]),
        qty=1,
        pnl=dir_sign * move * MES.point_value,
    ))

re_edge = random_entry(edge_trades, bars, n_iterations=5_000, seed=42)
re_noise = random_entry(noise_trades, bars, n_iterations=5_000, seed=42)

print(f"\n{APP_NAME} — Random-Entry Benchmark (edge vs noise)")
print("─" * 52)
print(
    f"  EDGE  : net ${re_edge.strategy_net:>10,.2f}"
    f"  | rank {re_edge.net_percentile_rank:.3f}"
    f"  | beats? {'✓ YES' if re_edge.beats_random else '✗ NO'}"
)
print(
    f"  NOISE : net ${re_noise.strategy_net:>10,.2f}"
    f"  | rank {re_noise.net_percentile_rank:.3f}"
    f"  | beats? {'✓ YES' if re_noise.beats_random else '✗ NO'}"
)
print(f"\n  Random P50 (same for both runs, seed=42): ${re_edge.random_net_pctiles[50]:,.2f}")
print(f"  Random P95: ${re_edge.random_net_pctiles[95]:,.2f}")

out = Path("reports/demo_benchmarks.html")
write_report(
    metrics,
    out,
    buy_hold=bh,
    random_entry_result=re_edge,
    meta={
        "Symbol": "MES",
        "Timeframe": "1day synthetic bars",
        "Bars": str(len(bars.df)),
        "Trades (buy-hold section)": str(len(tv_trades)),
        "Trades (random-entry section)": f"{N_DEMO} bar-consistent, EDGE profile",
    },
)
print(f"\nReport written → {out}")
