from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from backtester.ingest.firstrate import BarSet
from backtester.ingest.models import Trade
from backtester.instruments import MES, Instrument
from backtester.metrics.core import compute_metrics


class BenchmarkError(ValueError):
    """Raised when a benchmark cannot be computed (e.g. bars don't cover the trade range)."""


@dataclass(frozen=True)
class BuyHoldResult:
    strategy_net: float
    buy_hold_net: float
    beats_buy_hold: bool
    start_price: float
    end_price: float
    start_time: datetime
    end_time: datetime
    instrument_symbol: str


def buy_and_hold(
    trades: list[Trade],
    bars: BarSet,
    *,
    instrument: Instrument = MES,
    qty: int = 1,
) -> BuyHoldResult:
    """Compare strategy net profit against a buy-and-hold baseline.

    Strategy range = [min(entry_time), max(exit_time)] over all trades.
    Picks the first bar AT/AFTER range start and the last bar AT/BEFORE range end.
    buy_hold_net = (end_close - start_close) * instrument.point_value * qty.

    Note: this is a directional baseline only — did the strategy outperform holding
    the instrument? It is NOT a like-for-like exposure comparison. Use the random-entry
    benchmark (TASK 007) for that.

    Raises BenchmarkError if bars don't cover the trade range.
    """
    if not trades:
        raise BenchmarkError("trades list is empty.")

    range_start = min(t.entry_time for t in trades)
    range_end = max(t.exit_time for t in trades)

    def _to_utc(dt: datetime) -> pd.Timestamp:
        ts = pd.Timestamp(dt)
        if ts.tzinfo is None:
            raise BenchmarkError(f"Trade timestamp {dt!r} is not timezone-aware.")
        return ts.tz_convert("UTC")

    start_utc = _to_utc(range_start)
    end_utc = _to_utc(range_end)

    df = bars.df

    after_mask = df.index >= start_utc
    if not after_mask.any():
        raise BenchmarkError(
            f"bars don't cover trade range: no bar at or after {start_utc}. "
            f"Bar range ends at {df.index[-1]}."
        )

    before_mask = df.index <= end_utc
    if not before_mask.any():
        raise BenchmarkError(
            f"bars don't cover trade range: no bar at or before {end_utc}. "
            f"Bar range starts at {df.index[0]}."
        )

    start_bar_ts = df.index[after_mask][0]
    end_bar_ts = df.index[before_mask][-1]

    start_close = float(df.loc[start_bar_ts, "close"])
    end_close = float(df.loc[end_bar_ts, "close"])

    buy_hold_net = (end_close - start_close) * instrument.point_value * qty
    strategy_net = compute_metrics(trades).net_profit

    return BuyHoldResult(
        strategy_net=round(strategy_net, 2),
        buy_hold_net=round(buy_hold_net, 2),
        beats_buy_hold=strategy_net > buy_hold_net,
        start_price=start_close,
        end_price=end_close,
        start_time=start_bar_ts.to_pydatetime(),
        end_time=end_bar_ts.to_pydatetime(),
        instrument_symbol=instrument.symbol,
    )


@dataclass(frozen=True)
class RandomEntryResult:
    n_iterations: int
    seed: int
    n_trades: int
    long_fraction: float
    strategy_net: float
    strategy_expectancy: float
    random_net_dist: list[float]          # one net per random run
    random_net_pctiles: dict[int, float]  # keys 5, 25, 50, 75, 95
    net_percentile_rank: float            # fraction of random nets < strategy_net, in [0, 1]
    threshold: float
    beats_random: bool                    # net_percentile_rank >= threshold


def random_entry(
    trades: list[Trade],
    bars: BarSet,
    *,
    n_iterations: int = 10_000,
    seed: int = 42,
    instrument: Instrument = MES,
    qty: int = 1,
    threshold: float = 0.95,
) -> RandomEntryResult:
    """Compare strategy net against random entries sharing the same exposure profile.

    For each iteration, places n random entries drawn uniformly from the bar index, with
    holding periods sampled from the strategy's actual hold distribution (in bars), and
    direction sampled via Bernoulli(long_fraction). Works in bar-index space to avoid
    tz/DST coupling.

    VALIDITY: only meaningful when bars are the same instrument and period as the trades
    (true in normal use: ES trades + ES bars). The caller is responsible for passing
    consistent data.

    Raises BenchmarkError if trades is empty or bars has fewer than 2 rows.
    """
    if not trades:
        raise BenchmarkError("trades list is empty.")

    df = bars.df
    if len(df) < 2:
        raise BenchmarkError(
            f"bars must have at least 2 rows for random-entry simulation; got {len(df)}."
        )

    closes = df["close"].to_numpy()
    bar_index = df.index  # UTC DatetimeIndex
    last_bar = len(closes) - 1

    # ── Derive exposure profile ───────────────────────────────────────────────
    n = len(trades)
    long_count = sum(1 for t in trades if t.direction == "long")
    long_fraction = long_count / n

    def _to_utc(dt: datetime) -> pd.Timestamp:
        ts = pd.Timestamp(dt)
        if ts.tzinfo is None:
            raise BenchmarkError(f"Trade timestamp {dt!r} is not timezone-aware.")
        return ts.tz_convert("UTC")

    holds: list[int] = []
    for t in trades:
        entry_pos = min(int(bar_index.searchsorted(_to_utc(t.entry_time), side="left")), last_bar)
        exit_pos = min(int(bar_index.searchsorted(_to_utc(t.exit_time), side="left")), last_bar)
        holds.append(max(1, exit_pos - entry_pos))

    holds_arr = np.array(holds, dtype=np.int64)

    # ── Simulate — fully vectorised across all iterations ────────────────────
    rng = np.random.default_rng(seed)
    all_entry = rng.integers(0, last_bar, size=(n_iterations, n))           # [0, last_bar-1]
    all_holds = rng.choice(holds_arr, size=(n_iterations, n))
    all_exit = np.minimum(all_entry + all_holds, last_bar)
    all_dirs = np.where(rng.random(size=(n_iterations, n)) < long_fraction, 1.0, -1.0)

    all_pnls = (
        all_dirs
        * (closes[all_exit] - closes[all_entry])
        * instrument.point_value
        * qty
    )
    random_nets = all_pnls.sum(axis=1)  # shape: (n_iterations,)

    # ── Statistics ───────────────────────────────────────────────────────────
    m = compute_metrics(trades)
    strategy_net = m.net_profit
    strategy_expectancy = m.expectancy

    pctile_keys = [5, 25, 50, 75, 95]
    random_net_pctiles = {k: float(np.percentile(random_nets, k)) for k in pctile_keys}
    net_percentile_rank = float(np.mean(random_nets < strategy_net))

    return RandomEntryResult(
        n_iterations=n_iterations,
        seed=seed,
        n_trades=n,
        long_fraction=long_fraction,
        strategy_net=round(strategy_net, 2),
        strategy_expectancy=round(strategy_expectancy, 2),
        random_net_dist=random_nets.tolist(),
        random_net_pctiles=random_net_pctiles,
        net_percentile_rank=net_percentile_rank,
        threshold=threshold,
        beats_random=net_percentile_rank >= threshold,
    )
