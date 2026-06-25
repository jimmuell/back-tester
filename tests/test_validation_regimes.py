from __future__ import annotations

import pandas as pd

from backtester.ingest.firstrate import BarSet
from backtester.ingest.models import Trade
from backtester.ingest.synthetic import generate_bars
from backtester.instruments import MES
from backtester.validation.regimes import classify_regimes, regime_breakdown

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_trade(
    bars: BarSet,
    entry_idx: int,
    exit_idx: int,
    direction: str = "long",
    trade_id: int = 1,
) -> Trade:
    """Build a trade from bar timestamps and prices."""
    closes = bars.df["close"].to_numpy()
    ts = bars.df.index
    dir_sign = 1 if direction == "long" else -1
    pnl = dir_sign * (closes[exit_idx] - closes[entry_idx]) * MES.point_value
    return Trade(
        trade_id=trade_id,
        direction=direction,
        entry_time=ts[entry_idx].to_pydatetime(),
        exit_time=ts[exit_idx].to_pydatetime(),
        entry_price=float(closes[entry_idx]),
        exit_price=float(closes[exit_idx]),
        qty=1,
        pnl=pnl,
    )


def _mixed_vol_bars(n_low: int = 100, n_high: int = 100) -> BarSet:
    """Two-segment BarSet: quiet then turbulent. The split is clear enough to test."""
    low = generate_bars(n_bars=n_low, seed=1, daily_vol=0.001, drift=0.0)
    high = generate_bars(n_bars=n_high, seed=2, daily_vol=0.05, drift=0.0)

    # Stitch: adjust the high-vol segment so prices continue from the low-vol end
    last_close = low.df["close"].iloc[-1]
    first_close_high = high.df["close"].iloc[0]
    scale = last_close / first_close_high

    high_df = high.df.copy()
    for col in ["open", "high", "low", "close"]:
        high_df[col] = high_df[col] * scale

    # Shift timestamps so segments don't overlap
    shift = pd.Timedelta(days=n_low + 5)
    high_df.index = high_df.index + shift

    combined = pd.concat([low.df, high_df])
    combined.index.name = "timestamp"
    return BarSet(symbol="ES", timeframe="1day", adjustment="ratio", df=combined)


# ── Trend scheme: bull / bear dominance ───────────────────────────────────────

def test_trend_bull_dominant_for_uptrend() -> None:
    """A strongly upward-drifting series is predominantly labelled 'bull'."""
    bars = generate_bars(n_bars=200, seed=42, drift=0.005, daily_vol=0.005)
    labels = classify_regimes(bars, scheme="trend", ma_length=20)
    counts = labels.value_counts()
    bull_count = counts.get("bull", 0)
    # Expect bull to dominate after the warm-up (ma_length=20 bars of "undefined")
    assert bull_count > 100, f"Expected > 100 bull bars, got {bull_count}"


def test_trend_bear_dominant_for_downtrend() -> None:
    """A strongly downward-drifting series is predominantly labelled 'bear'."""
    bars = generate_bars(n_bars=200, seed=42, drift=-0.005, daily_vol=0.005)
    labels = classify_regimes(bars, scheme="trend", ma_length=20)
    counts = labels.value_counts()
    bear_count = counts.get("bear", 0)
    assert bear_count > 100, f"Expected > 100 bear bars, got {bear_count}"


def test_trend_undefined_fills_warmup() -> None:
    """First ma_length + 1 bars should be 'undefined' (SMA needs ma_length, diff needs one more)."""
    bars = generate_bars(n_bars=100, seed=42)
    ma_length = 30
    labels = classify_regimes(bars, scheme="trend", ma_length=ma_length)
    undefined_count = (labels == "undefined").sum()
    # SMA needs ma_length bars (indices 0..ma_length-2 are NaN); diff then needs one more valid SMA.
    # Result: has_data becomes True starting at index ma_length, so ma_length bars are "undefined".
    assert undefined_count == ma_length


def test_trend_labels_are_valid_strings() -> None:
    bars = generate_bars(n_bars=100, seed=42)
    labels = classify_regimes(bars, scheme="trend", ma_length=10)
    valid = {"bull", "bear", "range", "undefined"}
    assert set(labels.unique()).issubset(valid)


# ── Volatility scheme ─────────────────────────────────────────────────────────

def test_volatility_high_vol_segment_dominates_turbulent_window() -> None:
    """High-vol bars in the turbulent segment should be labelled 'high_vol' more than low_vol."""
    bars = _mixed_vol_bars(n_low=100, n_high=100)
    labels = classify_regimes(bars, scheme="volatility", vol_length=10, high_vol_quantile=0.67)

    # The second half (turbulent) should have more high_vol than the first half
    high_vol_in_turbulent = (labels.iloc[100:] == "high_vol").sum()
    high_vol_in_quiet = (labels.iloc[:100] == "high_vol").sum()
    assert high_vol_in_turbulent > high_vol_in_quiet, (
        f"turbulent high_vol={high_vol_in_turbulent}, quiet high_vol={high_vol_in_quiet}"
    )


def test_volatility_labels_are_valid_strings() -> None:
    bars = generate_bars(n_bars=100, seed=42)
    labels = classify_regimes(bars, scheme="volatility", vol_length=10)
    valid = {"high_vol", "low_vol", "undefined"}
    assert set(labels.unique()).issubset(valid)


# ── NON-LOOK-AHEAD (critical) ─────────────────────────────────────────────────

def test_non_look_ahead_trend() -> None:
    """Labels on a prefix must be identical to those from the full series — no future peeking."""
    full = generate_bars(n_bars=150, seed=42)
    prefix_df = full.df.iloc[:100].copy()
    prefix = BarSet(
        symbol=full.symbol, timeframe=full.timeframe,
        adjustment=full.adjustment, df=prefix_df,
    )

    full_labels = classify_regimes(full, scheme="trend", ma_length=20)
    prefix_labels = classify_regimes(prefix, scheme="trend", ma_length=20)

    pd.testing.assert_series_equal(
        full_labels.iloc[:100].reset_index(drop=True),
        prefix_labels.reset_index(drop=True),
        check_names=False,
    )


def test_non_look_ahead_volatility() -> None:
    """Expanding quantile threshold is trailing — later bars must not change earlier labels."""
    full = generate_bars(n_bars=150, seed=42)
    prefix_df = full.df.iloc[:100].copy()
    prefix = BarSet(
        symbol=full.symbol, timeframe=full.timeframe,
        adjustment=full.adjustment, df=prefix_df,
    )

    full_labels = classify_regimes(full, scheme="volatility", vol_length=10)
    prefix_labels = classify_regimes(prefix, scheme="volatility", vol_length=10)

    pd.testing.assert_series_equal(
        full_labels.iloc[:100].reset_index(drop=True),
        prefix_labels.reset_index(drop=True),
        check_names=False,
    )


# ── regime_breakdown: bucketing ───────────────────────────────────────────────

def test_trade_counts_sum_to_len_trades() -> None:
    bars = generate_bars(n_bars=200, seed=42, drift=0.003)
    trades = [_make_trade(bars, i, min(i + 3, 199)) for i in range(0, 60, 3)]
    rb = regime_breakdown(trades, bars, scheme="trend", ma_length=20.0)
    assert sum(rb.trade_counts.values()) == len(trades)


def test_per_regime_keys_match_trade_counts() -> None:
    bars = generate_bars(n_bars=200, seed=42, drift=0.003)
    trades = [_make_trade(bars, i, min(i + 3, 199), trade_id=i + 1) for i in range(0, 50, 5)]
    rb = regime_breakdown(trades, bars, scheme="trend", ma_length=20.0)
    # Every key in per_regime must appear in trade_counts
    assert set(rb.per_regime.keys()) == set(rb.trade_counts.keys())


def test_trade_in_known_bull_window_lands_in_bull() -> None:
    """A trade placed at a confirmed 'bull' bar should be bucketed in 'bull'."""
    bars = generate_bars(n_bars=200, seed=42, drift=0.005, daily_vol=0.005)
    labels = classify_regimes(bars, scheme="trend", ma_length=20)

    # Find the first "bull" bar index
    bull_positions = [i for i, lbl in enumerate(labels) if lbl == "bull"]
    assert bull_positions, "No bull bars found — drift too low?"
    entry_idx = bull_positions[0]
    exit_idx = min(entry_idx + 1, 199)

    trade = _make_trade(bars, entry_idx, exit_idx)
    rb = regime_breakdown([trade], bars, scheme="trend", ma_length=20.0)
    assert rb.trade_counts.get("bull", 0) == 1
    assert "bull" in rb.per_regime


def test_regime_breakdown_scheme_carried() -> None:
    bars = generate_bars(n_bars=100, seed=42)
    trades = [_make_trade(bars, 10, 15)]
    rb = regime_breakdown(trades, bars, scheme="volatility", vol_length=10.0)
    assert rb.scheme == "volatility"


# ── Determinism ───────────────────────────────────────────────────────────────

def test_classify_regimes_deterministic() -> None:
    bars = generate_bars(n_bars=100, seed=42)
    l1 = classify_regimes(bars, scheme="trend")
    l2 = classify_regimes(bars, scheme="trend")
    pd.testing.assert_series_equal(l1, l2)


def test_regime_breakdown_deterministic() -> None:
    bars = generate_bars(n_bars=150, seed=42, drift=0.003)
    trades = [_make_trade(bars, i, min(i + 3, 149), trade_id=i + 1) for i in range(0, 40, 4)]
    rb1 = regime_breakdown(trades, bars, scheme="trend", ma_length=30.0)
    rb2 = regime_breakdown(trades, bars, scheme="trend", ma_length=30.0)
    assert rb1.trade_counts == rb2.trade_counts
    assert set(rb1.per_regime.keys()) == set(rb2.per_regime.keys())
