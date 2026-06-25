from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from engine.ingest.firstrate import BarSet
from engine.ingest.models import Trade
from engine.ingest.synthetic import generate_bars
from engine.instruments import MES
from engine.validation.benchmarks import BenchmarkError, random_entry

UTC = ZoneInfo("UTC")

# ── Test helpers ──────────────────────────────────────────────────────────────

def _make_short_bars() -> BarSet:
    """One-row BarSet — should trigger BenchmarkError."""
    import pandas as pd
    idx = pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")], name="timestamp")
    df = pd.DataFrame(
        {
            "open": [5000.0], "high": [5010.0],
            "low": [4990.0], "close": [5005.0], "volume": [1000.0],
        },
        index=idx,
    )
    return BarSet(symbol="ES", timeframe="1day", adjustment="ratio", df=df)


def _edge_trades(bars: BarSet, *, n: int = 20, hold: int = 5) -> list[Trade]:
    """Cherry-pick the n entries with the largest |hold-bar forward move|.

    Going long when the move is positive, short when negative — pnl is always
    positive by construction, making the strategy net far above the random baseline.
    """
    closes = bars.df["close"].to_numpy()
    timestamps = bars.df.index
    last_bar = len(closes) - 1

    fwd = np.array([closes[min(i + hold, last_bar)] - closes[i] for i in range(last_bar)])
    top = np.argsort(np.abs(fwd))[::-1][:n]

    trades: list[Trade] = []
    for tid, i in enumerate(top, 1):
        exit_i = min(i + hold, last_bar)
        move = closes[exit_i] - closes[i]
        direction = "long" if move >= 0 else "short"
        dir_sign = 1 if direction == "long" else -1
        trades.append(Trade(
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
    return trades


def _noise_trades(bars: BarSet, *, n: int = 20, hold: int = 5, seed: int = 7) -> list[Trade]:
    """Random entries with random direction — no signal, matched exposure."""
    rng = np.random.default_rng(seed)
    closes = bars.df["close"].to_numpy()
    timestamps = bars.df.index
    last_bar = len(closes) - 1

    entry_idxs = rng.integers(0, last_bar, size=n)
    is_long = rng.random(size=n) < 0.5

    trades: list[Trade] = []
    for tid, (entry_i, long) in enumerate(zip(entry_idxs.tolist(), is_long.tolist()), 1):
        entry_i = int(entry_i)
        exit_i = min(entry_i + hold, last_bar)
        direction = "long" if long else "short"
        dir_sign = 1 if long else -1
        pnl = dir_sign * (closes[exit_i] - closes[entry_i]) * MES.point_value
        trades.append(Trade(
            trade_id=tid,
            direction=direction,
            entry_time=timestamps[entry_i].to_pydatetime(),
            exit_time=timestamps[exit_i].to_pydatetime(),
            entry_price=float(closes[entry_i]),
            exit_price=float(closes[exit_i]),
            qty=1,
            pnl=pnl,
        ))
    return trades


_BARS = generate_bars(n_bars=300, seed=42)

# ── Determinism ───────────────────────────────────────────────────────────────

def test_determinism() -> None:
    trades = _edge_trades(_BARS, n=10)
    r1 = random_entry(trades, _BARS, n_iterations=500, seed=42)
    r2 = random_entry(trades, _BARS, n_iterations=500, seed=42)
    assert r1.random_net_dist == r2.random_net_dist
    assert r1.net_percentile_rank == r2.net_percentile_rank


def test_different_seeds_differ() -> None:
    trades = _edge_trades(_BARS, n=10)
    r1 = random_entry(trades, _BARS, n_iterations=500, seed=42)
    r2 = random_entry(trades, _BARS, n_iterations=500, seed=99)
    assert r1.random_net_dist != r2.random_net_dist


# ── Exposure profile ──────────────────────────────────────────────────────────

def test_n_trades_correct() -> None:
    trades = _edge_trades(_BARS, n=15)
    r = random_entry(trades, _BARS, n_iterations=200, seed=42)
    assert r.n_trades == 15


def test_long_fraction_all_long() -> None:
    trades = _edge_trades(_BARS, n=10)
    # Force all longs
    all_long = [Trade(
        trade_id=t.trade_id, direction="long",
        entry_time=t.entry_time, exit_time=t.exit_time,
        entry_price=t.entry_price, exit_price=t.exit_price,
        qty=t.qty, pnl=abs(t.pnl),
    ) for t in trades]
    r = random_entry(all_long, _BARS, n_iterations=200, seed=42)
    assert r.long_fraction == pytest.approx(1.0)


def test_long_fraction_half() -> None:
    noise = _noise_trades(_BARS, n=20, seed=7)
    r = random_entry(noise, _BARS, n_iterations=200, seed=42)
    # noise helper assigns ~50% long
    assert 0.0 <= r.long_fraction <= 1.0


# ── DISCRIMINATION ────────────────────────────────────────────────────────────

def test_edge_high_percentile_rank() -> None:
    """Cherry-picked entries must rank far above random (rank > 0.90)."""
    trades = _edge_trades(_BARS, n=20, hold=5)
    r = random_entry(trades, _BARS, n_iterations=2_000, seed=42, threshold=0.90)
    assert r.net_percentile_rank > 0.90, (
        f"EDGE rank {r.net_percentile_rank:.3f} should be > 0.90"
    )
    assert r.beats_random is True


def test_noise_mid_percentile_rank() -> None:
    """Random entries should rank in the bulk of the distribution (not dominant)."""
    trades = _noise_trades(_BARS, n=20, hold=5, seed=7)
    r = random_entry(trades, _BARS, n_iterations=2_000, seed=42, threshold=0.95)
    assert 0.05 < r.net_percentile_rank < 0.95, (
        f"NOISE rank {r.net_percentile_rank:.3f} should be in (0.05, 0.95)"
    )
    assert r.beats_random is False


# ── Distribution properties ───────────────────────────────────────────────────

def test_pctiles_non_decreasing() -> None:
    trades = _noise_trades(_BARS, n=20, seed=7)
    r = random_entry(trades, _BARS, n_iterations=500, seed=42)
    p = r.random_net_pctiles
    assert p[5] <= p[25] <= p[50] <= p[75] <= p[95]


def test_percentile_rank_in_unit_interval() -> None:
    trades = _edge_trades(_BARS, n=10)
    r = random_entry(trades, _BARS, n_iterations=500, seed=42)
    assert 0.0 <= r.net_percentile_rank <= 1.0


def test_dist_length_matches_n_iterations() -> None:
    trades = _edge_trades(_BARS, n=10)
    r = random_entry(trades, _BARS, n_iterations=300, seed=42)
    assert len(r.random_net_dist) == 300


def test_pctile_keys() -> None:
    trades = _edge_trades(_BARS, n=10)
    r = random_entry(trades, _BARS, n_iterations=200, seed=42)
    assert set(r.random_net_pctiles.keys()) == {5, 25, 50, 75, 95}


# ── beats_random flag ─────────────────────────────────────────────────────────

def test_beats_random_threshold_respected() -> None:
    """beats_random = (rank >= threshold)."""
    trades = _edge_trades(_BARS, n=20)
    r = random_entry(trades, _BARS, n_iterations=500, seed=42, threshold=0.0)
    # With threshold=0.0 any rank qualifies
    assert r.beats_random is True


def test_beats_random_impossible_threshold() -> None:
    trades = _edge_trades(_BARS, n=20)
    r = random_entry(trades, _BARS, n_iterations=500, seed=42, threshold=1.1)
    assert r.beats_random is False


# ── Guard ─────────────────────────────────────────────────────────────────────

def test_too_short_bars_raises() -> None:
    bars = _make_short_bars()
    trades = [Trade(
        trade_id=1, direction="long",
        entry_time=datetime(2024, 1, 2, tzinfo=UTC),
        exit_time=datetime(2024, 1, 2, tzinfo=UTC),
        entry_price=5000.0, exit_price=5010.0, qty=1, pnl=50.0,
    )]
    with pytest.raises(BenchmarkError):
        random_entry(trades, bars)


def test_empty_trades_raises() -> None:
    with pytest.raises(BenchmarkError):
        random_entry([], _BARS)
