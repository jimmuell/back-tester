from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np

from engine.ingest.models import Trade
from engine.instruments import MES, Instrument
from engine.timeutils import ET

# Single source of truth for the TradingView "List of Trades" CSV columns.
TRADINGVIEW_COLUMNS = [
    "Trade #",
    "Type",
    "Signal",
    "Date/Time",
    "Price",
    "Contracts",
    "Profit",
    "Profit %",
    "Cum. Profit",
    "Run-up",
    "Drawdown",
]

_RTH_OPEN = (9, 30)   # 09:30 ET
_RTH_CLOSE = (16, 0)  # 16:00 ET
_RTH_MINUTES = (16 * 60) - (9 * 60 + 30)  # 390 minutes


def _is_weekday(d: date) -> bool:
    return d.weekday() < 5


def _rth_time(d: date, rng: np.random.Generator, margin_minutes: int = 30) -> datetime:
    """Return a random tz-aware datetime within RTH, keeping margin from open/close."""
    lo = margin_minutes
    hi = _RTH_MINUTES - margin_minutes
    minute_offset = int(rng.integers(lo, hi))
    t = datetime(d.year, d.month, d.day, _RTH_OPEN[0], _RTH_OPEN[1], tzinfo=ET)
    return t + timedelta(minutes=minute_offset)


def _profile_params(
    profile: Literal["edge", "noise", "negative"],
    win_rate_override: float | None,
) -> tuple[float, float, float]:
    """Return (win_rate, avg_win_points, avg_loss_points) for the given profile."""
    if profile == "edge":
        win_rate = win_rate_override if win_rate_override is not None else 0.40
        avg_win = 10.0   # points — ~2.5× the avg loss
        avg_loss = 4.0
    elif profile == "noise":
        win_rate = win_rate_override if win_rate_override is not None else 0.50
        avg_win = 4.0
        avg_loss = 4.0
    else:  # negative
        win_rate = win_rate_override if win_rate_override is not None else 0.35
        avg_win = 3.0
        avg_loss = 6.0
    return win_rate, avg_win, avg_loss


def generate_trades(
    n_trades: int = 200,
    *,
    profile: Literal["edge", "noise", "negative"] = "edge",
    instrument: Instrument = MES,
    seed: int = 42,
    start_date: date = date(2024, 1, 2),
    trades_per_day: int = 4,
    win_rate: float | None = None,
    commission_per_contract: float = 1.24,
    qty: int = 1,
    start_id: int = 1,
) -> list[Trade]:
    """Generate a reproducible synthetic trade list.

    start_id lets callers produce non-overlapping ID ranges when concatenating
    multiple batches for CSV round-trips (e.g. start_id=n_first+1 for the
    second batch avoids duplicate Trade # errors in load_trades).
    """
    rng = np.random.default_rng(seed)
    wr, avg_win_pts, avg_loss_pts = _profile_params(profile, win_rate)

    trades: list[Trade] = []
    current_date = start_date
    trade_id = start_id

    while len(trades) < n_trades:
        if not _is_weekday(current_date):
            current_date += timedelta(days=1)
            continue

        day_trades = min(trades_per_day, n_trades - len(trades))
        # Spread trades evenly across the RTH session
        entry_minutes = sorted(
            int(x) for x in rng.integers(30, _RTH_MINUTES - 60, size=day_trades)
        )

        for i, entry_min in enumerate(entry_minutes):
            entry_dt = datetime(
                current_date.year, current_date.month, current_date.day,
                _RTH_OPEN[0], _RTH_OPEN[1], tzinfo=ET,
            ) + timedelta(minutes=int(entry_min))

            hold_minutes = int(rng.integers(5, 45))
            exit_dt = entry_dt + timedelta(minutes=hold_minutes)
            if exit_dt.hour >= _RTH_CLOSE[0]:
                exit_dt = datetime(
                    current_date.year, current_date.month, current_date.day,
                    _RTH_CLOSE[0] - 1, 55, tzinfo=ET,
                )

            is_win = rng.random() < wr
            direction: Literal["long", "short"] = "long" if rng.random() < 0.5 else "short"
            entry_price = round(float(rng.uniform(4800.0, 5200.0)), 2)

            if is_win:
                pts = float(rng.exponential(avg_win_pts))
                pts = max(pts, instrument.tick_size)
                move = pts if direction == "long" else -pts
            else:
                pts = float(rng.exponential(avg_loss_pts))
                pts = max(pts, instrument.tick_size)
                move = -pts if direction == "long" else pts

            exit_price = round(entry_price + move, 2)
            gross = (exit_price - entry_price) * instrument.point_value * qty
            if direction == "short":
                gross = -gross
            commission = commission_per_contract * qty * 2  # entry + exit
            net_pnl = round(gross - commission, 2)

            trades.append(Trade(
                trade_id=trade_id,
                direction=direction,
                entry_time=entry_dt,
                exit_time=exit_dt,
                entry_price=entry_price,
                exit_price=exit_price,
                qty=qty,
                pnl=net_pnl,
            ))
            trade_id += 1

        current_date += timedelta(days=1)

    return trades


def write_tradingview_csv(trades: list[Trade], path: Path) -> None:
    """Write trades in the standard TradingView 'List of Trades' CSV format (2 rows per trade)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cum_profit = 0.0

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRADINGVIEW_COLUMNS)
        writer.writeheader()

        for t in trades:
            cum_profit += t.pnl
            entry_signal = "Long Entry" if t.direction == "long" else "Short Entry"
            exit_signal = "Long Exit" if t.direction == "long" else "Short Exit"
            dt_fmt = "%Y-%m-%d %H:%M"

            # Entry row — no profit
            writer.writerow({
                "Trade #": t.trade_id,
                "Type": "Entry",
                "Signal": entry_signal,
                "Date/Time": t.entry_time.strftime(dt_fmt),
                "Price": f"{t.entry_price:.2f}",
                "Contracts": t.qty,
                "Profit": "",
                "Profit %": "",
                "Cum. Profit": "",
                "Run-up": "",
                "Drawdown": "",
            })
            # Exit row — carries P&L
            writer.writerow({
                "Trade #": t.trade_id,
                "Type": "Exit",
                "Signal": exit_signal,
                "Date/Time": t.exit_time.strftime(dt_fmt),
                "Price": f"{t.exit_price:.2f}",
                "Contracts": t.qty,
                "Profit": f"{t.pnl:.2f}",
                "Profit %": "",
                "Cum. Profit": f"{cum_profit:.2f}",
                "Run-up": "",
                "Drawdown": "",
            })
