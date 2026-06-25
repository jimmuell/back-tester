from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from engine.ingest.synthetic import generate_trades, write_tradingview_csv


def test_reproducible_same_seed() -> None:
    a = generate_trades(n_trades=50, seed=42)
    b = generate_trades(n_trades=50, seed=42)
    assert a == b


def test_different_seeds_differ() -> None:
    a = generate_trades(n_trades=50, seed=42)
    b = generate_trades(n_trades=50, seed=99)
    assert a != b


def test_edge_positive_expectancy() -> None:
    trades = generate_trades(n_trades=500, profile="edge", seed=42)
    mean_pnl = sum(t.pnl for t in trades) / len(trades)
    assert mean_pnl > 0, f"Edge profile expectancy should be positive, got {mean_pnl:.4f}"


def test_noise_gross_near_zero_before_commission() -> None:
    # noise profile: win_rate=0.5, avg_win ≈ avg_loss → gross near zero
    # We check the gross PNL (before commission), which requires reconstructing it.
    trades = generate_trades(
        n_trades=1000,
        profile="noise",
        seed=0,
        commission_per_contract=0.0,   # zero commission → net == gross
    )
    mean_gross = sum(t.pnl for t in trades) / len(trades)
    # Allow ±1.50 per trade: symmetric noise around 0
    assert abs(mean_gross) < 1.50, (
        f"Noise profile (zero commission) mean pnl should be near 0, got {mean_gross:.4f}"
    )


def test_negative_expectancy() -> None:
    trades = generate_trades(n_trades=500, profile="negative", seed=42)
    mean_pnl = sum(t.pnl for t in trades) / len(trades)
    assert mean_pnl < 0, f"Negative profile expectancy should be <0, got {mean_pnl:.4f}"


def test_trade_count() -> None:
    trades = generate_trades(n_trades=100)
    assert len(trades) == 100


def test_direction_valid() -> None:
    trades = generate_trades(n_trades=50, seed=1)
    for t in trades:
        assert t.direction in ("long", "short")


def test_trade_ids_unique_sequential() -> None:
    trades = generate_trades(n_trades=50, seed=42)
    ids = [t.trade_id for t in trades]
    assert ids == list(range(1, 51))


def test_write_csv_two_rows_per_trade() -> None:
    trades = generate_trades(n_trades=20, seed=42)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        csv_path = Path(f.name)
    write_tradingview_csv(trades, csv_path)

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 2 * len(trades), "Expected 2 rows per trade"


def test_write_csv_pnl_on_exit_row() -> None:
    trades = generate_trades(n_trades=10, seed=42)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = Path(f.name)
    write_tradingview_csv(trades, csv_path)

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for i in range(0, len(rows), 2):
        entry_row = rows[i]
        exit_row = rows[i + 1]
        assert entry_row["Type"] == "Entry"
        assert exit_row["Type"] == "Exit"
        assert entry_row["Profit"] == "", "Entry row should have no Profit"
        assert exit_row["Profit"] != "", "Exit row must carry Profit"


def test_write_csv_trade_numbers_paired() -> None:
    trades = generate_trades(n_trades=15, seed=5)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = Path(f.name)
    write_tradingview_csv(trades, csv_path)

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for i in range(0, len(rows), 2):
        assert rows[i]["Trade #"] == rows[i + 1]["Trade #"], "Entry/exit must share Trade #"
