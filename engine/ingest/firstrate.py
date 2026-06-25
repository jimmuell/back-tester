"""
FirstRate ES futures bar-data loader (ADR-006).

FirstRate format:
- CSV, US/Eastern timestamps, NO header by default (auto-detected).
- Columns: timestamp, open, high, low, close, volume
- 1day files append a 7th column: open_interest
- Zero-volume bars are omitted by the vendor.
- Continuous series adjustment is metadata supplied by the caller; it cannot
  be inferred from the price data.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd

Timeframe = Literal["1min", "5min", "30min", "1hour", "1day"]
Adjustment = Literal["unadjusted", "ratio", "absolute"]

_INTRADAY_COLS = ["open", "high", "low", "close", "volume"]
_DAILY_COLS = ["open", "high", "low", "close", "volume", "open_interest"]

# Ordered from most to least specific so the first match wins.
_DT_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%Y-%m-%d",
    "%m/%d/%Y",
]


class BarDataError(ValueError):
    """Raised when a FirstRate CSV cannot be loaded cleanly."""


@dataclass(frozen=True)
class BarSet:
    symbol: str
    timeframe: Timeframe
    adjustment: Adjustment
    df: pd.DataFrame   # UTC-indexed DatetimeIndex named "timestamp"


def _try_parse_dt(value: str) -> bool:
    """Return True if value parses as any known datetime format."""
    for fmt in _DT_FORMATS:
        try:
            pd.Timestamp(value)   # fast path
            return True
        except Exception:
            pass
        try:
            pd.to_datetime(value, format=fmt)
            return True
        except Exception:
            continue
    return False


def _parse_timestamps(raw: pd.Series, source_tz: ZoneInfo) -> pd.DatetimeIndex:
    """
    Parse a Series of timestamp strings into a UTC-aware DatetimeIndex.
    Tries each known format in order; raises BarDataError on failure.
    """
    for fmt in _DT_FORMATS:
        try:
            parsed = pd.to_datetime(raw, format=fmt, utc=False)
            # Attach source tz then convert to UTC
            local = parsed.dt.tz_localize(source_tz)
            return pd.DatetimeIndex(local.dt.tz_convert("UTC"))
        except Exception:
            continue
    raise BarDataError(
        f"Cannot parse timestamps — tried formats {_DT_FORMATS}. "
        f"Sample value: {raw.iloc[0]!r}"
    )


def load_bars(
    path: Path,
    *,
    timeframe: Timeframe,
    adjustment: Adjustment = "ratio",
    symbol: str = "ES",
    source_tz: str = "America/New_York",
) -> BarSet:
    """
    Load a FirstRate ES futures CSV into a BarSet.

    Timestamps are localized to source_tz and converted to UTC.
    The returned DataFrame has a UTC-aware DatetimeIndex named "timestamp"
    and float columns for OHLCV (plus open_interest for 1day).

    Raises BarDataError on: wrong column count, unparseable timestamps,
    duplicate timestamps, or OHLC sanity violations.
    """
    tz = ZoneInfo(source_tz)
    is_daily = timeframe == "1day"
    expected_data_cols = _DAILY_COLS if is_daily else _INTRADAY_COLS
    n_data_cols = len(expected_data_cols)   # 6 or 5 (excl. timestamp)

    # ── Read raw ─────────────────────────────────────────────────────────────
    if Path(path).stat().st_size == 0:
        raise BarDataError(f"{path} is empty.")

    try:
        raw = pd.read_csv(path, header=None, dtype=str)
    except Exception as exc:
        raise BarDataError(f"Cannot read {path}: {exc}") from exc

    if raw.empty:
        raise BarDataError(f"{path} is empty.")

    # ── Auto-detect header ────────────────────────────────────────────────────
    # If the first cell of row 0 doesn't look like a datetime, treat row 0 as a header.
    first_cell = str(raw.iloc[0, 0]).strip()
    has_header = not _try_parse_dt(first_cell)
    if has_header:
        raw = raw.iloc[1:].reset_index(drop=True)

    if raw.empty:
        raise BarDataError(f"{path} has only a header row and no data.")

    # ── Column count check ────────────────────────────────────────────────────
    # Expect 1 (timestamp) + n_data_cols, or occasionally n_data_cols+1+1 with OI.
    n_cols = raw.shape[1]
    expected_total = 1 + n_data_cols      # 7 for 1day, 6 for intraday
    if n_cols != expected_total:
        raise BarDataError(
            f"Expected {expected_total} columns for timeframe={timeframe!r} "
            f"(1 timestamp + {n_data_cols} data), got {n_cols}. "
            f"File: {path}"
        )

    # ── Parse timestamps ──────────────────────────────────────────────────────
    ts_index = _parse_timestamps(raw.iloc[:, 0], tz)

    # ── Duplicate check ───────────────────────────────────────────────────────
    dupes = ts_index[ts_index.duplicated()]
    if not dupes.empty:
        raise BarDataError(
            f"Duplicate timestamps in {path}: {dupes.tolist()[:5]}"
        )

    # ── Build DataFrame ───────────────────────────────────────────────────────
    data = raw.iloc[:, 1:].copy()
    data.columns = pd.Index(expected_data_cols)
    try:
        data = data.astype(float)
    except ValueError as exc:
        raise BarDataError(f"Non-numeric OHLCV data in {path}: {exc}") from exc

    df = data.copy()
    df.index = ts_index
    df.index.name = "timestamp"
    df = df.sort_index()

    # ── OHLC sanity ───────────────────────────────────────────────────────────
    bad_high = df["high"] < df[["open", "close", "low"]].max(axis=1)
    bad_low = df["low"] > df[["open", "close", "high"]].min(axis=1)
    violations = bad_high | bad_low
    if violations.any():
        first_bad = df.index[violations][0]
        row = df.loc[first_bad]
        raise BarDataError(
            f"OHLC sanity violation at {first_bad}: "
            f"O={row['open']} H={row['high']} L={row['low']} C={row['close']}"
        )

    return BarSet(
        symbol=symbol,
        timeframe=timeframe,
        adjustment=adjustment,
        df=df,
    )
