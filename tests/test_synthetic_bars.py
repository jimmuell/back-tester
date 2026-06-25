from __future__ import annotations

from datetime import date

import pandas as pd

from engine.ingest.synthetic import generate_bars


def test_default_row_count() -> None:
    bs = generate_bars()
    assert len(bs.df) == 252


def test_reproducible() -> None:
    bs1 = generate_bars(seed=42)
    bs2 = generate_bars(seed=42)
    pd.testing.assert_frame_equal(bs1.df, bs2.df)


def test_different_seeds_differ() -> None:
    bs1 = generate_bars(seed=42)
    bs2 = generate_bars(seed=99)
    assert not bs1.df["close"].equals(bs2.df["close"])


def test_symbol_carried() -> None:
    bs = generate_bars(symbol="MES")
    assert bs.symbol == "MES"


def test_timeframe_carried() -> None:
    bs = generate_bars(timeframe="5min")
    assert bs.timeframe == "5min"


def test_adjustment_carried() -> None:
    bs = generate_bars(adjustment="unadjusted")
    assert bs.adjustment == "unadjusted"


def test_utc_aware_index() -> None:
    bs = generate_bars()
    assert bs.df.index.tz is not None
    assert str(bs.df.index.tz) == "UTC"


def test_index_named_timestamp() -> None:
    bs = generate_bars()
    assert bs.df.index.name == "timestamp"


def test_index_sorted_ascending() -> None:
    bs = generate_bars()
    assert bs.df.index.is_monotonic_increasing


def test_columns_ohlcv() -> None:
    bs = generate_bars()
    assert list(bs.df.columns) == ["open", "high", "low", "close", "volume"]


def test_all_columns_float() -> None:
    bs = generate_bars()
    for col in bs.df.columns:
        assert bs.df[col].dtype == float, f"column {col} is not float"


def test_ohlc_high_invariant_1day() -> None:
    bs = generate_bars(n_bars=252)
    df = bs.df
    assert (df["high"] >= df[["open", "close", "low"]].max(axis=1)).all()


def test_ohlc_low_invariant_1day() -> None:
    bs = generate_bars(n_bars=252)
    df = bs.df
    assert (df["low"] <= df[["open", "close", "high"]].min(axis=1)).all()


def test_ohlc_high_invariant_5min() -> None:
    bs = generate_bars(timeframe="5min", n_bars=100)
    df = bs.df
    assert (df["high"] >= df[["open", "close", "low"]].max(axis=1)).all()


def test_ohlc_low_invariant_5min() -> None:
    bs = generate_bars(timeframe="5min", n_bars=100)
    df = bs.df
    assert (df["low"] <= df[["open", "close", "high"]].min(axis=1)).all()


def test_volume_positive() -> None:
    bs = generate_bars()
    assert (bs.df["volume"] > 0).all()


def test_5min_n_bars() -> None:
    bs = generate_bars(timeframe="5min", n_bars=78)
    assert len(bs.df) == 78


def test_custom_n_bars() -> None:
    bs = generate_bars(n_bars=50)
    assert len(bs.df) == 50


def test_custom_start_date() -> None:
    bs = generate_bars(start=date(2024, 3, 1))  # Friday — first weekday
    assert bs.df.index[0].date() == date(2024, 3, 1)


def test_1day_timestamps_are_weekdays() -> None:
    bs = generate_bars(n_bars=20)
    for ts in bs.df.index:
        assert ts.weekday() < 5, f"{ts} is not a weekday"


def test_5min_timestamps_within_rth() -> None:
    bs = generate_bars(timeframe="5min", n_bars=78)
    for ts in bs.df.index:
        hour_utc = ts.hour
        minute_utc = ts.minute
        total_min = hour_utc * 60 + minute_utc
        # RTH 09:30–16:00 ET = 14:30–21:00 UTC (EST)
        assert 14 * 60 + 30 <= total_min < 21 * 60
