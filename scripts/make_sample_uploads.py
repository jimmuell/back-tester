"""Write sample trade list and bar data CSVs to /tmp for manual UI testing.

Usage:
    python scripts/make_sample_uploads.py [--profile edge|noise] [--n-trades N] [--n-bars N]

Output:
    /tmp/sample_trades.csv   — TradingView List of Trades format
    /tmp/sample_bars.csv     — FirstRate daily format (date,o,h,l,c,volume,open_interest)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtester.ingest.synthetic import generate_bars, generate_trades, write_tradingview_csv


def write_firstrate_csv(bars_path: Path, n_bars: int, seed: int) -> None:
    bar_set = generate_bars(n_bars=n_bars, seed=seed, drift=0.001, daily_vol=0.01)
    df = bar_set.df.copy()
    df.index = df.index.tz_convert("America/New_York").normalize()
    with bars_path.open("w", newline="") as f:
        writer = csv.writer(f)
        for ts, row in df.iterrows():
            date_str = ts.strftime("%Y-%m-%d")
            writer.writerow([
                date_str,
                f"{row['open']:.2f}",
                f"{row['high']:.2f}",
                f"{row['low']:.2f}",
                f"{row['close']:.2f}",
                f"{int(row['volume'])}",
                "0",
            ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="edge", choices=["edge", "noise"])
    parser.add_argument("--n-trades", type=int, default=200)
    parser.add_argument("--n-bars", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="/tmp")
    args = parser.parse_args()

    out = Path(args.out_dir)
    trades_path = out / "sample_trades.csv"
    bars_path = out / "sample_bars.csv"

    trades = generate_trades(n_trades=args.n_trades, profile=args.profile, seed=args.seed)
    write_tradingview_csv(trades, trades_path)
    print(f"Trades ({args.n_trades}, profile={args.profile}): {trades_path}")

    write_firstrate_csv(bars_path, n_bars=args.n_bars, seed=args.seed)
    print(f"Bars ({args.n_bars} daily bars): {bars_path}")

    print()
    print("Upload both files at http://localhost:3000 with the backend running on :8000")


if __name__ == "__main__":
    main()
