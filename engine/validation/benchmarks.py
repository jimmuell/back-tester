from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from engine.ingest.firstrate import BarSet
from engine.ingest.models import Trade
from engine.instruments import MES, Instrument
from engine.metrics.core import compute_metrics


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
