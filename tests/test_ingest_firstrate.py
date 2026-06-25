from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from backtester.ingest.firstrate import BarDataError, load_bars

FIXTURES = Path(__file__).parent / "fixtures"
F5MIN = FIXTURES / "es_5min_sample.csv"
F1DAY = FIXTURES / "es_1day_sample.csv"
FHEADER = FIXTURES / "es_5min_withheader.csv"


# ── Basic load ────────────────────────────────────────────────────────────────

def test_5min_row_count() -> None:
    bs = load_bars(F5MIN, timeframe="5min")
    assert len(bs.df) == 10


def test_5min_columns() -> None:
    bs = load_bars(F5MIN, timeframe="5min")
    assert list(bs.df.columns) == ["open", "high", "low", "close", "volume"]


def test_5min_index_utc_aware() -> None:
    bs = load_bars(F5MIN, timeframe="5min")
    assert bs.df.index.tz is not None
    assert str(bs.df.index.tz) == "UTC"


def test_5min_index_named_timestamp() -> None:
    bs = load_bars(F5MIN, timeframe="5min")
    assert bs.df.index.name == "timestamp"


def test_5min_index_sorted_ascending() -> None:
    bs = load_bars(F5MIN, timeframe="5min")
    assert bs.df.index.is_monotonic_increasing


def test_5min_ohlcv_are_float() -> None:
    bs = load_bars(F5MIN, timeframe="5min")
    for col in bs.df.columns:
        assert bs.df[col].dtype == float, f"column {col} is not float"


# ── 1day fixture ──────────────────────────────────────────────────────────────

def test_1day_row_count() -> None:
    bs = load_bars(F1DAY, timeframe="1day")
    assert len(bs.df) == 8


def test_1day_has_open_interest_column() -> None:
    bs = load_bars(F1DAY, timeframe="1day")
    assert "open_interest" in bs.df.columns


def test_5min_has_no_open_interest_column() -> None:
    bs = load_bars(F5MIN, timeframe="5min")
    assert "open_interest" not in bs.df.columns


# ── Header auto-detection ─────────────────────────────────────────────────────

def test_header_file_loads_same_data_as_no_header() -> None:
    no_hdr = load_bars(F5MIN, timeframe="5min")
    with_hdr = load_bars(FHEADER, timeframe="5min")
    pd.testing.assert_frame_equal(no_hdr.df, with_hdr.df)


# ── TZ correctness ────────────────────────────────────────────────────────────

def test_known_et_timestamp_maps_to_correct_utc() -> None:
    """2024-01-02 09:30 ET (EST = UTC-5) → 2024-01-02 14:30 UTC."""
    bs = load_bars(F5MIN, timeframe="5min")
    first = bs.df.index[0]
    assert first == pd.Timestamp("2024-01-02 14:30:00", tz="UTC")


def test_1day_date_maps_to_utc() -> None:
    """2024-01-02 date (no time) localised as midnight ET → 05:00 UTC."""
    bs = load_bars(F1DAY, timeframe="1day")
    first = bs.df.index[0]
    assert first == pd.Timestamp("2024-01-02 05:00:00", tz="UTC")


# ── BarSet metadata ───────────────────────────────────────────────────────────

def test_barset_carries_symbol() -> None:
    bs = load_bars(F5MIN, timeframe="5min", symbol="MES")
    assert bs.symbol == "MES"


def test_barset_default_symbol() -> None:
    bs = load_bars(F5MIN, timeframe="5min")
    assert bs.symbol == "ES"


def test_barset_carries_timeframe() -> None:
    bs = load_bars(F5MIN, timeframe="5min")
    assert bs.timeframe == "5min"


def test_barset_default_adjustment_is_ratio() -> None:
    bs = load_bars(F5MIN, timeframe="5min")
    assert bs.adjustment == "ratio"


def test_barset_custom_adjustment() -> None:
    bs = load_bars(F5MIN, timeframe="5min", adjustment="unadjusted")
    assert bs.adjustment == "unadjusted"


# ── Error cases ───────────────────────────────────────────────────────────────

def _write_tmp(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w", newline=""
    )
    f.write(textwrap.dedent(content))
    f.close()
    return Path(f.name)


def test_duplicate_timestamps_raises() -> None:
    p = _write_tmp("""\
        2024-01-02 09:30:00,4780.50,4785.25,4778.00,4783.75,3842
        2024-01-02 09:30:00,4783.75,4790.00,4782.50,4788.25,2915
    """)
    with pytest.raises(BarDataError, match="[Dd]uplicate"):
        load_bars(p, timeframe="5min")
    p.unlink()


def test_ohlc_high_below_open_raises() -> None:
    # high=4770 < open=4780.50 → violation
    p = _write_tmp("""\
        2024-01-02 09:30:00,4780.50,4770.00,4765.00,4768.00,3842
    """)
    with pytest.raises(BarDataError, match="[Oo]HLC"):
        load_bars(p, timeframe="5min")
    p.unlink()


def test_ohlc_low_above_close_raises() -> None:
    # low=4800 > close=4783.75 → violation
    p = _write_tmp("""\
        2024-01-02 09:30:00,4780.50,4810.00,4800.00,4783.75,3842
    """)
    with pytest.raises(BarDataError, match="[Oo]HLC"):
        load_bars(p, timeframe="5min")
    p.unlink()


def test_wrong_column_count_intraday_raises() -> None:
    # Only 5 cols (missing volume) for an intraday file
    p = _write_tmp("""\
        2024-01-02 09:30:00,4780.50,4785.25,4778.00,4783.75
    """)
    with pytest.raises(BarDataError, match="[Cc]olumn"):
        load_bars(p, timeframe="5min")
    p.unlink()


def test_wrong_column_count_daily_raises() -> None:
    # Only 6 cols for a 1day file (missing open_interest)
    p = _write_tmp("""\
        2024-01-02,4780.50,4812.75,4775.00,4802.25,312450
    """)
    with pytest.raises(BarDataError, match="[Cc]olumn"):
        load_bars(p, timeframe="1day")
    p.unlink()


def test_empty_file_raises() -> None:
    p = _write_tmp("")
    with pytest.raises(BarDataError, match="[Ee]mpty"):
        load_bars(p, timeframe="5min")
    p.unlink()
