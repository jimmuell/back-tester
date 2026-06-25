from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backtester.ingest.models import Trade
from backtester.ingest.synthetic import generate_trades
from backtester.timeutils import ET
from backtester.validation.splits import in_out_split


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
    """
    Concatenation of an early edge block and a later negative block.
    When split chronologically, IS should be positive and OOS negative.
    """
    early = generate_trades(n_trades=100, profile="edge", seed=1,
                            start_date=datetime(2024, 1, 2).date())
    late = generate_trades(n_trades=100, profile="negative", seed=2,
                           start_date=datetime(2024, 8, 1).date())
    return early + late


# ── Partition correctness ─────────────────────────────────────────────────────

def test_partition_size_default_30pct() -> None:
    """IS gets 70% and OOS gets 30% of trades (rounded)."""
    trades = [_trade(i, 10.0, i) for i in range(1, 11)]   # 10 trades
    result = in_out_split(trades, oos_fraction=0.30)
    n_is = result.split_index
    n_oos = len(trades) - n_is
    assert n_is == 7
    assert n_oos == 3


def test_partition_is_chronological() -> None:
    """Trades should be sorted by exit_time; the last IS trade precedes all OOS trades."""
    trades = [_trade(i, 10.0, 10 - i) for i in range(1, 11)]  # reverse-chronological order
    result = in_out_split(trades, oos_fraction=0.30)
    # split_time = exit_time of last IS trade; all OOS exit_times must be >= split_time
    assert result.out_sample.total_trades == 3


def test_split_time_is_last_is_exit() -> None:
    # 10 trades, oos_fraction=0.20 → split_idx=8, last IS trade has exit_offset_days=8
    # base=Jan 2 + 8 days = Jan 10
    trades = [_trade(i, 5.0, i) for i in range(1, 11)]
    result = in_out_split(trades, oos_fraction=0.20)
    from datetime import datetime as _dt
    base = _dt(2024, 1, 2, 10, 0, tzinfo=ET)
    from datetime import timedelta as _td
    expected = (base + _td(days=8)).day    # Jan 10
    assert result.split_time.day == expected


def test_segment_sizes_sum_to_total() -> None:
    trades = generate_trades(n_trades=200, seed=42)
    result = in_out_split(trades, oos_fraction=0.25)
    assert result.in_sample.total_trades + result.out_sample.total_trades == 200


# ── Edge / decay verdict ──────────────────────────────────────────────────────

def test_edge_profile_not_decayed() -> None:
    """A consistent edge profile should NOT be flagged as decayed."""
    trades = generate_trades(n_trades=300, profile="edge", seed=42)
    result = in_out_split(trades)
    # OOS expectancy should still be positive for a genuine edge over 300 trades
    assert not result.edge_decayed, (
        f"Edge profile flagged as decayed: IS={result.in_sample.expectancy:.2f} "
        f"OOS={result.out_sample.expectancy:.2f}"
    )


def test_decaying_series_flagged() -> None:
    """A strategy that degrades over time should be flagged edge_decayed=True."""
    trades = _decaying_trades()
    result = in_out_split(trades)
    assert result.edge_decayed, (
        f"Decaying series NOT flagged: IS={result.in_sample.expectancy:.2f} "
        f"OOS={result.out_sample.expectancy:.2f}"
    )


def test_decaying_expectancy_ratio_lt_1() -> None:
    trades = _decaying_trades()
    result = in_out_split(trades)
    assert result.expectancy_ratio < 1.0, (
        f"Expectancy ratio should be < 1 for a decaying series, got {result.expectancy_ratio:.4f}"
    )


def test_expectancy_ratio_consistent_edge() -> None:
    """For a consistently positive edge, ratio should be positive (same sign)."""
    trades = generate_trades(n_trades=400, profile="edge", seed=7)
    result = in_out_split(trades)
    assert result.expectancy_ratio > 0, (
        f"Consistent edge should have positive ratio, got {result.expectancy_ratio:.4f}"
    )


# ── Guards ────────────────────────────────────────────────────────────────────

def test_empty_trades_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        in_out_split([])


def test_invalid_oos_fraction_zero_raises() -> None:
    trades = [_trade(1, 10.0, 1)]
    with pytest.raises(ValueError, match="oos_fraction"):
        in_out_split(trades, oos_fraction=0.0)


def test_invalid_oos_fraction_one_raises() -> None:
    trades = [_trade(1, 10.0, 1)]
    with pytest.raises(ValueError, match="oos_fraction"):
        in_out_split(trades, oos_fraction=1.0)


def test_too_few_trades_for_split_raises() -> None:
    # 1 trade, 0.30 OOS → split_idx = round(0.70) = 1 → leaves no OOS
    trades = [_trade(1, 10.0, 1)]
    with pytest.raises(ValueError):
        in_out_split(trades, oos_fraction=0.30)
