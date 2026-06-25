from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backtester.ingest.models import Trade
from backtester.ingest.synthetic import generate_trades
from backtester.timeutils import ET
from backtester.validation.walkforward import walk_forward


def _trade(trade_id: int, pnl: float, exit_offset_days: int) -> Trade:
    base = datetime(2024, 1, 2, 10, 0, tzinfo=ET)
    entry = base + timedelta(days=exit_offset_days, hours=-1)
    exit_ = base + timedelta(days=exit_offset_days)
    return Trade(
        trade_id=trade_id,
        direction="long",
        entry_time=entry,
        entry_price=5000.0,
        exit_time=exit_,
        exit_price=5001.0,
        qty=1,
        pnl=pnl,
    )


def _decaying_trades() -> list[Trade]:
    early = generate_trades(n_trades=150, profile="edge", seed=1,
                            start_date=datetime(2024, 1, 2).date())
    late = generate_trades(n_trades=150, profile="negative", seed=2,
                           start_date=datetime(2024, 9, 1).date())
    return early + late


# ── Partition correctness ─────────────────────────────────────────────────────

def test_window_count_matches_n_windows() -> None:
    trades = generate_trades(n_trades=100, seed=42)
    result = walk_forward(trades, n_windows=5)
    assert len(result.windows) == 5
    assert result.n_windows == 5


def test_all_trades_covered() -> None:
    """Sum of per-window trade counts must equal total trades."""
    trades = generate_trades(n_trades=97, seed=42)
    result = walk_forward(trades, n_windows=5)
    assert sum(w.n_trades for w in result.windows) == 97


def test_windows_are_time_ordered() -> None:
    """start_time of window i+1 must be >= end_time of window i."""
    trades = generate_trades(n_trades=100, seed=3)
    result = walk_forward(trades, n_windows=5)
    for a, b in zip(result.windows, result.windows[1:]):
        assert b.start_time >= a.end_time


def test_windows_are_contiguous_non_overlapping() -> None:
    """Windows must be contiguous: window[i].end_time < window[i+1].start_time or equal."""
    trades = [_trade(i, float(i), i) for i in range(1, 21)]
    result = walk_forward(trades, n_windows=4)
    starts = [w.start_time for w in result.windows]
    ends = [w.end_time for w in result.windows]
    for i in range(len(result.windows) - 1):
        assert ends[i] <= starts[i + 1]


def test_scheme_label() -> None:
    trades = generate_trades(n_trades=40, seed=0)
    result = walk_forward(trades, n_windows=4)
    assert result.scheme == "rolling"


def test_determinism() -> None:
    trades = generate_trades(n_trades=100, seed=42)
    a = walk_forward(trades, n_windows=5)
    b = walk_forward(trades, n_windows=5)
    assert [w.expectancy for w in a.windows] == [w.expectancy for w in b.windows]


# ── Summary statistics ────────────────────────────────────────────────────────

def test_pct_windows_positive_in_unit_interval() -> None:
    trades = generate_trades(n_trades=100, seed=42)
    result = walk_forward(trades, n_windows=5)
    assert 0.0 <= result.pct_windows_positive <= 1.0


def test_expectancy_std_non_negative() -> None:
    trades = generate_trades(n_trades=100, seed=42)
    result = walk_forward(trades, n_windows=5)
    assert result.expectancy_std >= 0.0


def test_expectancy_mean_matches_windows() -> None:
    trades = generate_trades(n_trades=100, seed=42)
    result = walk_forward(trades, n_windows=5)
    manual_mean = sum(w.expectancy for w in result.windows) / 5
    assert abs(result.expectancy_mean - manual_mean) < 1e-9


# ── Decaying series detection ─────────────────────────────────────────────────

def test_decaying_series_pct_positive_lt_1() -> None:
    """A decaying series should have some negative-expectancy windows."""
    trades = _decaying_trades()
    result = walk_forward(trades, n_windows=6)
    assert result.pct_windows_positive < 1.0, (
        f"Decaying series should have some negative windows, "
        f"got pct_positive={result.pct_windows_positive:.1%}"
    )


def test_decaying_series_declining_expectancy() -> None:
    """Later windows should have lower expectancy than earlier windows on average."""
    trades = _decaying_trades()
    result = walk_forward(trades, n_windows=6)
    early_avg = sum(w.expectancy for w in result.windows[:3]) / 3
    late_avg = sum(w.expectancy for w in result.windows[3:]) / 3
    assert late_avg < early_avg, (
        f"Expected later windows to have lower expectancy: "
        f"early_avg={early_avg:.2f}, late_avg={late_avg:.2f}"
    )


# ── Guards ────────────────────────────────────────────────────────────────────

def test_empty_trades_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        walk_forward([])


def test_n_windows_less_than_2_raises() -> None:
    trades = generate_trades(n_trades=10, seed=0)
    with pytest.raises(ValueError, match="n_windows"):
        walk_forward(trades, n_windows=1)


def test_n_windows_greater_than_trades_raises() -> None:
    trades = [_trade(i, 10.0, i) for i in range(1, 4)]  # 3 trades
    with pytest.raises(ValueError, match="n_windows"):
        walk_forward(trades, n_windows=5)
