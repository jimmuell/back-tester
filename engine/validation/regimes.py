from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import numpy as np
import pandas as pd

from engine.ingest.firstrate import BarSet
from engine.ingest.models import Trade
from engine.metrics.core import Metrics, compute_metrics

RegimeScheme = Literal["trend", "volatility"]


def classify_regimes(
    bars: BarSet,
    *,
    scheme: RegimeScheme = "trend",
    ma_length: int = 50,
    vol_length: int = 20,
    high_vol_quantile: float = 0.67,
) -> pd.Series:
    """Return a string Series of regime labels aligned to bars.df.index.

    NON-LOOK-AHEAD: every label uses only data up to and including that bar.
    Bars without enough history are labelled "undefined".

    scheme="trend":
        sma = close.rolling(ma_length).mean(); slope = sma.diff()
        "bull"  if close > sma and slope > 0
        "bear"  if close < sma and slope < 0
        "range" otherwise (has data, but mixed signal)
        "undefined" until the SMA and its diff are both available.

    scheme="volatility":
        ret = log(close).diff(); rv = ret.rolling(vol_length).std()
        threshold = rv.expanding().quantile(high_vol_quantile)  ← trailing, non-look-ahead
        "high_vol" if rv >= threshold; "low_vol" otherwise.
        "undefined" until vol_length bars of returns are available.
    """
    close = bars.df["close"]

    if scheme == "trend":
        sma = close.rolling(ma_length).mean()
        slope = sma.diff()
        has_data = sma.notna() & slope.notna()

        bull_mask = has_data & (close > sma) & (slope > 0)
        bear_mask = has_data & (close < sma) & (slope < 0)

        arr = np.select(
            [bear_mask.to_numpy(), bull_mask.to_numpy(), has_data.to_numpy()],
            ["bear", "bull", "range"],
            default="undefined",
        )

    elif scheme == "volatility":
        ret = np.log(close).diff()
        rv = ret.rolling(vol_length).std()
        # expanding().quantile() ignores NaN by default — trailing and non-look-ahead
        threshold = rv.expanding().quantile(high_vol_quantile)

        has_data = rv.notna()
        high_vol_mask = has_data & (rv >= threshold)

        arr = np.select(
            [high_vol_mask.to_numpy(), has_data.to_numpy()],
            ["high_vol", "low_vol"],
            default="undefined",
        )

    else:
        raise ValueError(f"Unknown scheme {scheme!r}; expected 'trend' or 'volatility'.")

    return pd.Series(arr, index=bars.df.index, name="regime", dtype=object)


@dataclass(frozen=True)
class RegimeBreakdown:
    scheme: str
    params: dict[str, float]
    per_regime: dict[str, Metrics]   # regime label → metrics for that regime's trades
    trade_counts: dict[str, int]     # sum equals len(trades)


def regime_breakdown(
    trades: list[Trade],
    bars: BarSet,
    *,
    scheme: RegimeScheme = "trend",
    **params: float,
) -> RegimeBreakdown:
    """Bucket trades by the bar regime at/before their entry time and compute per-bucket metrics.

    For each trade, the regime label is taken from the most recent bar AT/BEFORE entry_time
    (searchsorted side="right" minus 1, clamped to 0). Trades falling before the first bar
    get the first bar's label; trades after the last bar get the last bar's label.

    trade_counts sums to len(trades).
    """
    ma_length = int(params.get("ma_length", 50))
    vol_length = int(params.get("vol_length", 20))
    high_vol_quantile = float(params.get("high_vol_quantile", 0.67))

    regimes = classify_regimes(
        bars,
        scheme=scheme,
        ma_length=ma_length,
        vol_length=vol_length,
        high_vol_quantile=high_vol_quantile,
    )
    bar_index = bars.df.index

    def _to_utc(dt: datetime) -> pd.Timestamp:
        ts = pd.Timestamp(dt)
        if ts.tzinfo is None:
            raise ValueError(f"Trade timestamp {dt!r} is not timezone-aware.")
        return ts.tz_convert("UTC")

    buckets: dict[str, list[Trade]] = {}
    trade_counts: dict[str, int] = {}

    for t in trades:
        entry_utc = _to_utc(t.entry_time)
        # side="right": returns position after all equal elements → subtract 1 for AT/BEFORE
        pos = int(bar_index.searchsorted(entry_utc, side="right")) - 1
        pos = max(0, pos)
        label = str(regimes.iloc[pos])

        buckets.setdefault(label, []).append(t)
        trade_counts[label] = trade_counts.get(label, 0) + 1

    per_regime = {lbl: compute_metrics(tlist) for lbl, tlist in buckets.items()}
    param_dict = {k: v for k, v in params.items()}

    return RegimeBreakdown(
        scheme=scheme,
        params=param_dict,
        per_regime=per_regime,
        trade_counts=trade_counts,
    )
