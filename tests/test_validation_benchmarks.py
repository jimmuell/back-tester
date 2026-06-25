from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from backtester.ingest.firstrate import BarSet
from backtester.ingest.models import Trade
from backtester.instruments import MES
from backtester.validation.benchmarks import BenchmarkError, buy_and_hold

UTC = ZoneInfo("UTC")


def _make_bars(closes: list[float], start: str = "2024-01-02") -> BarSet:
    """Build a minimal 1day BarSet with given close prices, business-day UTC index."""
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq="B", tz="UTC")
    opens = [c * 0.999 for c in closes]
    highs = [c * 1.005 for c in closes]
    lows = [c * 0.995 for c in closes]
    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1000.0] * n,
        },
        index=dates,
    )
    df.index.name = "timestamp"
    return BarSet(symbol="ES", timeframe="1day", adjustment="ratio", df=df)


def _make_trade(
    entry_time: datetime,
    exit_time: datetime,
    pnl: float = 100.0,
    trade_id: int = 1,
) -> Trade:
    return Trade(
        trade_id=trade_id,
        direction="long",
        entry_time=entry_time,
        exit_time=exit_time,
        entry_price=5000.0,
        exit_price=5010.0,
        qty=1,
        pnl=pnl,
    )


# ── buy_hold_net calculation ──────────────────────────────────────────────────

def test_buy_hold_net_matches_hand_calc() -> None:
    # 5 business-day bars: 2024-01-02 → 2024-01-08 (Mon–Mon)
    # start_close=5000, end_close=5100, delta=100, MES point_value=5
    bars = _make_bars([5000.0, 5025.0, 5050.0, 5075.0, 5100.0])
    entry = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    exit_ = datetime(2024, 1, 8, 0, 0, tzinfo=UTC)
    trades = [_make_trade(entry, exit_, pnl=50.0)]
    result = buy_and_hold(trades, bars, instrument=MES, qty=1)
    expected = (5100.0 - 5000.0) * MES.point_value * 1
    assert result.buy_hold_net == pytest.approx(expected)


def test_buy_hold_net_qty_2() -> None:
    bars = _make_bars([5000.0, 5100.0])
    entry = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    exit_ = datetime(2024, 1, 3, 0, 0, tzinfo=UTC)
    trades = [_make_trade(entry, exit_, pnl=50.0)]
    result = buy_and_hold(trades, bars, instrument=MES, qty=2)
    expected = (5100.0 - 5000.0) * MES.point_value * 2
    assert result.buy_hold_net == pytest.approx(expected)


def test_buy_hold_net_negative_move() -> None:
    # declining bars: buy-and-hold loses money
    bars = _make_bars([5100.0, 5000.0])
    entry = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    exit_ = datetime(2024, 1, 3, 0, 0, tzinfo=UTC)
    trades = [_make_trade(entry, exit_, pnl=50.0)]
    result = buy_and_hold(trades, bars, instrument=MES, qty=1)
    assert result.buy_hold_net == pytest.approx((5000.0 - 5100.0) * MES.point_value)
    assert result.buy_hold_net < 0


# ── beats_buy_hold flag ───────────────────────────────────────────────────────

def test_beats_buy_hold_true() -> None:
    # buy_hold_net = (5010-5000)*5 = 50; strategy_net = 999 → beats
    bars = _make_bars([5000.0, 5010.0])
    entry = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    exit_ = datetime(2024, 1, 3, 0, 0, tzinfo=UTC)
    trades = [_make_trade(entry, exit_, pnl=999.0)]
    result = buy_and_hold(trades, bars, instrument=MES, qty=1)
    assert result.beats_buy_hold is True


def test_beats_buy_hold_false() -> None:
    # buy_hold_net = (5100-5000)*5 = 500; strategy_net = 1 → does not beat
    bars = _make_bars([5000.0, 5100.0])
    entry = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    exit_ = datetime(2024, 1, 3, 0, 0, tzinfo=UTC)
    trades = [_make_trade(entry, exit_, pnl=1.0)]
    result = buy_and_hold(trades, bars, instrument=MES, qty=1)
    assert result.beats_buy_hold is False


def test_beats_buy_hold_exact_equal_is_false() -> None:
    # strategy_net == buy_hold_net → beats_buy_hold is False (strict >)
    bars = _make_bars([5000.0, 5100.0])
    entry = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    exit_ = datetime(2024, 1, 3, 0, 0, tzinfo=UTC)
    buy_hold_net = (5100.0 - 5000.0) * MES.point_value * 1  # 500
    trades = [_make_trade(entry, exit_, pnl=buy_hold_net)]
    result = buy_and_hold(trades, bars, instrument=MES, qty=1)
    assert result.beats_buy_hold is False


# ── result fields ─────────────────────────────────────────────────────────────

def test_result_carries_prices() -> None:
    bars = _make_bars([4900.0, 5000.0, 5100.0])
    entry = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    exit_ = datetime(2024, 1, 4, 0, 0, tzinfo=UTC)
    trades = [_make_trade(entry, exit_, pnl=50.0)]
    result = buy_and_hold(trades, bars, instrument=MES, qty=1)
    assert result.start_price == pytest.approx(4900.0)
    assert result.end_price == pytest.approx(5100.0)


def test_result_instrument_symbol() -> None:
    bars = _make_bars([5000.0, 5100.0])
    entry = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    exit_ = datetime(2024, 1, 3, 0, 0, tzinfo=UTC)
    trades = [_make_trade(entry, exit_)]
    result = buy_and_hold(trades, bars, instrument=MES, qty=1)
    assert result.instrument_symbol == "MES"


# ── error cases ───────────────────────────────────────────────────────────────

def test_bars_entirely_after_trade_range_raises() -> None:
    # bars start 2024-06-03, all trades end 2024-01-03 → no bar <= end_utc
    bars = _make_bars([5000.0, 5100.0], start="2024-06-03")
    entry = datetime(2024, 1, 2, 0, 0, tzinfo=UTC)
    exit_ = datetime(2024, 1, 3, 0, 0, tzinfo=UTC)
    trades = [_make_trade(entry, exit_)]
    with pytest.raises(BenchmarkError):
        buy_and_hold(trades, bars)


def test_bars_entirely_before_trade_range_raises() -> None:
    # bars end 2024-01-03, trade starts 2024-06-03 → no bar >= start_utc
    bars = _make_bars([5000.0, 5100.0], start="2024-01-02")
    entry = datetime(2024, 6, 3, 0, 0, tzinfo=UTC)
    exit_ = datetime(2024, 6, 4, 0, 0, tzinfo=UTC)
    trades = [_make_trade(entry, exit_)]
    with pytest.raises(BenchmarkError):
        buy_and_hold(trades, bars)


def test_empty_trades_raises() -> None:
    bars = _make_bars([5000.0, 5100.0])
    with pytest.raises(BenchmarkError):
        buy_and_hold([], bars)
