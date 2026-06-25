"""Slice 0 demo: synthetic edge trades → CSV → load → metrics → HTML report."""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from engine.config import APP_NAME
from engine.ingest.synthetic import generate_trades, write_tradingview_csv
from engine.ingest.tradingview import load_trades
from engine.metrics.core import compute_metrics
from engine.report.html import write_report

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORT_PATH = REPORTS_DIR / "sample_report.html"


def main() -> None:
    seed = 42
    n_trades = 200

    # 1. Generate synthetic edge trades
    trades = generate_trades(n_trades=n_trades, profile="edge", seed=seed)

    # 2. Write to a temp CSV (mimics a real TradingView export)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        csv_path = Path(tmp.name)
    write_tradingview_csv(trades, csv_path)

    # 3. Load through the TradingView loader
    loaded = load_trades(csv_path)
    csv_path.unlink(missing_ok=True)

    # 4. Compute metrics
    m = compute_metrics(loaded)

    # 5. Write HTML report
    meta = {
        "Profile": "edge",
        "Seed": str(seed),
        "Trades generated": str(n_trades),
        "Source": "synthetic (TradingView-format CSV)",
        "Generated at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    write_report(m, REPORT_PATH, meta=meta)

    # 6. Print KPI summary
    pf = f"{m.profit_factor:.2f}" if m.profit_factor != float("inf") else "inf"
    print(
        f"{APP_NAME} | trades={m.total_trades} win_rate={m.win_rate:.1%} "
        f"net=${m.net_profit:,.2f} expectancy=${m.expectancy:.2f} "
        f"profit_factor={pf} max_dd=${m.max_drawdown:,.2f}"
    )
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
