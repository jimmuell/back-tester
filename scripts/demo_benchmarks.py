#!/usr/bin/env python3
"""Demo: synthetic bars + buy-and-hold benchmark (TASK 006)."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from engine.ingest.synthetic import generate_bars, generate_trades
from engine.instruments import MES
from engine.metrics.core import compute_metrics
from engine.report.html import write_report
from engine.validation.benchmarks import buy_and_hold

APP_NAME = os.getenv("APP_NAME", "BackTester")

# 252 business-day bars starting 2024-01-02
bars = generate_bars(timeframe="1day", n_bars=252, seed=42, start=date(2024, 1, 2))

# 100 "edge" trades starting 2024-02-01 — well within the bar range
trades = generate_trades(n_trades=100, profile="edge", seed=42, start_date=date(2024, 2, 1))

bh = buy_and_hold(trades, bars, instrument=MES, qty=1)
metrics = compute_metrics(trades)

print(f"\n{APP_NAME} — Buy-and-Hold Benchmark Demo")
print("─" * 45)
print(f"  Strategy net profit : ${bh.strategy_net:,.2f}")
print(f"  Buy-and-hold net    : ${bh.buy_hold_net:,.2f}")
print(f"  Beats buy-and-hold  : {'✓ YES' if bh.beats_buy_hold else '✗ NO'}")
print(f"  Entry bar close     : {bh.start_price:,.2f}  ({bh.start_time.strftime('%Y-%m-%d')} UTC)")
print(f"  Exit bar close      : {bh.end_price:,.2f}  ({bh.end_time.strftime('%Y-%m-%d')} UTC)")
print(f"  Bars in BarSet      : {len(bars.df)}")
print(f"  Trades evaluated    : {len(trades)}")
print(f"  Strategy expectancy : ${metrics.expectancy:,.2f}/trade")

out = Path("reports/demo_benchmarks.html")
write_report(
    metrics,
    out,
    buy_hold=bh,
    meta={
        "Symbol": "MES",
        "Timeframe": "1day synthetic bars",
        "Bars": str(len(bars.df)),
        "Trades": str(len(trades)),
        "Profile": "edge",
    },
)
print(f"\nReport written → {out}")
