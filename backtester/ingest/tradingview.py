from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from backtester.ingest.models import Trade
from backtester.ingest.synthetic import TRADINGVIEW_COLUMNS

# Canonical column names — also the single source of truth shared with synthetic.py.
__all__ = ["TRADINGVIEW_COLUMNS", "TradeListFormatError", "load_trades"]


class TradeListFormatError(ValueError):
    """Raised when the CSV does not match the expected TradingView trade-list shape."""


def _normalise(name: str) -> str:
    """Lowercase + collapse whitespace for tolerant column matching."""
    return re.sub(r"\s+", " ", name.strip().lower())


# Tolerant aliases for column names we read (handles 'Profit' vs 'P&L' variants, etc.)
_COL_ALIASES: dict[str, str] = {
    "trade #": "trade_num",
    "trade#": "trade_num",
    "#": "trade_num",
    "type": "type",
    "signal": "signal",
    "date/time": "datetime",
    "date / time": "datetime",
    "datetime": "datetime",
    "price": "price",
    "contracts": "contracts",
    "qty": "contracts",
    "quantity": "contracts",
    "profit": "profit",
    "p&l": "profit",
    "pnl": "profit",
    "net profit": "profit",
}

_REQUIRED_CANONICAL = {"trade_num", "type", "datetime", "price", "contracts", "profit"}

_ENTRY_SIGNALS = {"entry", "long entry", "short entry", "buy", "sell short"}
_EXIT_SIGNALS = {"exit", "long exit", "short exit", "sell", "buy to cover"}
_LONG_SIGNALS = {"long entry", "buy"}
_SHORT_SIGNALS = {"short entry", "sell short"}

_DT_FORMATS = [
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %H:%M:%S",
]


def _parse_dt(raw: str, tz: ZoneInfo) -> datetime:
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=tz)
        except ValueError:
            continue
    raise TradeListFormatError(f"Unrecognised date/time format: {raw!r}")


def _parse_float(raw: str, col: str) -> float:
    try:
        return float(raw.strip().replace(",", ""))
    except ValueError as exc:
        raise TradeListFormatError(f"Cannot parse {col} as float: {raw!r}") from exc


def _map_columns(header: list[str]) -> dict[str, int]:
    """Return canonical_name → column_index mapping, raising on missing required columns."""
    mapping: dict[str, int] = {}
    for idx, name in enumerate(header):
        canonical = _COL_ALIASES.get(_normalise(name))
        if canonical and canonical not in mapping:
            mapping[canonical] = idx

    missing = _REQUIRED_CANONICAL - mapping.keys()
    if missing:
        raise TradeListFormatError(
            f"Missing required columns: {sorted(missing)}. "
            f"Got: {header}. "
            f"Expected TradingView 'List of Trades' format."
        )
    return mapping


def load_trades(path: Path, *, tz: str = "America/New_York") -> list[Trade]:
    """
    Load a TradingView 'List of Trades' CSV and return paired Trade records.

    Pairs entry/exit rows by Trade #. Tolerant of column-name variants and whitespace.
    Raises TradeListFormatError with a clear message on unrecognised shape.
    """
    timezone = ZoneInfo(tz)

    with open(path, newline="") as f:
        reader = csv.reader(f)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise TradeListFormatError("File is empty.") from exc

        col = _map_columns(raw_header)

        rows = list(reader)

    if not rows:
        raise TradeListFormatError("File has a header but no data rows.")

    # Collect entry and exit rows keyed by trade number
    entries: dict[int, dict[str, str]] = {}
    exits: dict[int, dict[str, str]] = {}

    for lineno, row in enumerate(rows, start=2):
        if len(row) < len(raw_header):
            row += [""] * (len(raw_header) - len(row))

        try:
            trade_num = int(row[col["trade_num"]])
        except ValueError as exc:
            raise TradeListFormatError(
                f"Line {lineno}: cannot parse Trade # as integer: {row[col['trade_num']]!r}"
            ) from exc

        row_type = _normalise(row[col["type"]])
        signal = _normalise(row[col.get("signal", col["type"])])

        record = {k: row[v] for k, v in col.items()}

        if row_type == "entry" or signal in _ENTRY_SIGNALS:
            if trade_num in entries:
                raise TradeListFormatError(
                    f"Line {lineno}: duplicate ENTRY for Trade #{trade_num}"
                )
            entries[trade_num] = record
        elif row_type == "exit" or signal in _EXIT_SIGNALS:
            if trade_num in exits:
                raise TradeListFormatError(
                    f"Line {lineno}: duplicate EXIT for Trade #{trade_num}"
                )
            exits[trade_num] = record
        else:
            raise TradeListFormatError(
                f"Line {lineno}: unrecognised Type/Signal: type={row[col['type']]!r}, "
                f"signal={row[col.get('signal', col['type'])]!r}"
            )

    unpaired = set(entries) ^ set(exits)
    if unpaired:
        raise TradeListFormatError(
            f"Unpaired trade numbers (missing entry or exit): {sorted(unpaired)}"
        )

    trades: list[Trade] = []
    for trade_num in sorted(entries):
        entry = entries[trade_num]
        exit_ = exits[trade_num]

        entry_signal = _normalise(entry.get("signal", ""))
        if entry_signal in _SHORT_SIGNALS:
            direction = "short"
        else:
            direction = "long"  # default

        profit_raw = exit_.get("profit", "").strip()
        if not profit_raw:
            raise TradeListFormatError(
                f"Trade #{trade_num}: exit row has no Profit value."
            )

        trades.append(Trade(
            trade_id=trade_num,
            direction=direction,  # type: ignore[arg-type]
            entry_time=_parse_dt(entry["datetime"], timezone),
            entry_price=_parse_float(entry["price"], "Price"),
            exit_time=_parse_dt(exit_["datetime"], timezone),
            exit_price=_parse_float(exit_["price"], "Price"),
            qty=int(float(entry["contracts"])),
            pnl=_parse_float(profit_raw, "Profit"),
        ))

    return trades
