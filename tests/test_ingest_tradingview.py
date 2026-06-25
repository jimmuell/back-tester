from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import pytest

from engine.ingest.synthetic import generate_trades, write_tradingview_csv
from engine.ingest.tradingview import TradeListFormatError, load_trades

FIXTURE = Path(__file__).parent / "fixtures" / "sample_trades_edge.csv"


def test_fixture_loads_correct_count() -> None:
    trades = load_trades(FIXTURE)
    assert len(trades) == 60


def test_fixture_all_trades_paired() -> None:
    trades = load_trades(FIXTURE)
    ids = [t.trade_id for t in trades]
    assert ids == sorted(set(ids)), "Trade IDs should be unique and ordered"


def test_fixture_direction_valid() -> None:
    trades = load_trades(FIXTURE)
    for t in trades:
        assert t.direction in ("long", "short")


def test_round_trip_same_trades() -> None:
    original = generate_trades(n_trades=30, seed=7, profile="edge")
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = Path(f.name)
    write_tradingview_csv(original, csv_path)
    loaded = load_trades(csv_path)
    csv_path.unlink(missing_ok=True)

    assert len(loaded) == len(original)
    for orig, lod in zip(original, loaded):
        assert orig.trade_id == lod.trade_id
        assert orig.direction == lod.direction
        assert abs(orig.entry_price - lod.entry_price) < 0.01
        assert abs(orig.exit_price - lod.exit_price) < 0.01
        assert abs(orig.pnl - lod.pnl) < 0.01
        assert orig.qty == lod.qty


def test_empty_file_raises() -> None:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        csv_path = Path(f.name)
    with pytest.raises(TradeListFormatError, match="empty"):
        load_trades(csv_path)
    csv_path.unlink(missing_ok=True)


def test_missing_column_raises() -> None:
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w", newline=""
    ) as f:
        csv_path = Path(f.name)
        writer = csv.writer(f)
        writer.writerow(["Trade #", "Type", "Date/Time"])  # missing Price, Contracts, Profit
        writer.writerow(["1", "Entry", "2024-01-02 09:30"])
    with pytest.raises(TradeListFormatError, match="Missing required columns"):
        load_trades(csv_path)
    csv_path.unlink(missing_ok=True)


def test_unrecognised_type_raises() -> None:
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w", newline=""
    ) as f:
        csv_path = Path(f.name)
        writer = csv.writer(f)
        writer.writerow(["Trade #", "Type", "Signal", "Date/Time", "Price", "Contracts", "Profit"])
        writer.writerow(["1", "Unknown", "???", "2024-01-02 09:30", "5000.00", "1", ""])
    with pytest.raises(TradeListFormatError):
        load_trades(csv_path)
    csv_path.unlink(missing_ok=True)


def test_unpaired_trade_raises() -> None:
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w", newline=""
    ) as f:
        csv_path = Path(f.name)
        writer = csv.writer(f)
        writer.writerow(["Trade #", "Type", "Signal", "Date/Time", "Price", "Contracts", "Profit"])
        # Only an entry row, no exit
        writer.writerow(["1", "Entry", "Long Entry", "2024-01-02 09:30", "5000.00", "1", ""])
    with pytest.raises(TradeListFormatError, match="[Uu]npaired"):
        load_trades(csv_path)
    csv_path.unlink(missing_ok=True)


def test_duplicate_entry_row_raises() -> None:
    """Two ENTRY rows for the same Trade # must raise, not silently overwrite."""
    cols = ["Trade #", "Type", "Signal", "Date/Time", "Price", "Contracts", "Profit"]
    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w", newline=""
    ) as f:
        csv_path = Path(f.name)
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerow(["1", "Entry", "Long Entry", "2024-01-02 09:30", "5000.00", "1", ""])
        writer.writerow(["1", "Entry", "Long Entry", "2024-01-02 09:45", "5001.00", "1", ""])
        writer.writerow(["1", "Exit",  "Long Exit",  "2024-01-02 10:00", "5010.00", "1", "50.00"])
    with pytest.raises(TradeListFormatError, match="duplicate"):
        load_trades(csv_path)
    csv_path.unlink(missing_ok=True)


def test_start_id_produces_expected_range() -> None:
    trades = generate_trades(n_trades=10, seed=1, start_id=51)
    ids = [t.trade_id for t in trades]
    assert ids == list(range(51, 61))


def test_two_batches_non_overlapping_ids_round_trip() -> None:
    """Two batches with disjoint ID ranges must survive write→load with no trades lost."""
    batch_a = generate_trades(n_trades=20, seed=1, start_id=1)
    batch_b = generate_trades(n_trades=15, seed=2, start_id=21,
                              start_date=__import__("datetime").date(2024, 6, 1))
    combined = batch_a + batch_b
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = Path(f.name)
    write_tradingview_csv(combined, csv_path)
    loaded = load_trades(csv_path)
    csv_path.unlink(missing_ok=True)
    assert len(loaded) == 35, f"Expected 35 trades, got {len(loaded)}"
