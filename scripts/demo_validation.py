"""Validation demo: edge (stable) vs decaying series (flagged)."""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from backtester.config import APP_NAME
from backtester.ingest.models import Trade
from backtester.ingest.synthetic import generate_trades, write_tradingview_csv
from backtester.ingest.tradingview import load_trades
from backtester.metrics.core import compute_metrics
from backtester.montecarlo.bootstrap import run_bootstrap
from backtester.montecarlo.shuffle import run_shuffle
from backtester.report.html import write_report
from backtester.validation.splits import in_out_split
from backtester.validation.walkforward import walk_forward

REPORTS_DIR = Path(__file__).parent.parent / "reports"


def _load_via_csv(trades: list[Trade]) -> list[Trade]:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        p = Path(f.name)
    write_tradingview_csv(trades, p)
    loaded = load_trades(p)
    p.unlink(missing_ok=True)
    return loaded


def _print_split(label: str, sp: object) -> None:
    from backtester.validation.splits import SplitResult
    assert isinstance(sp, SplitResult)
    flag = "⚠ DECAYED" if sp.edge_decayed else "  stable "
    ratio_str = (
        f"{sp.expectancy_ratio:.2f}×"
        if sp.expectancy_ratio == sp.expectancy_ratio  # NaN guard
        else "N/A"
    )
    print(
        f"  {label:35s} | IS exp={sp.in_sample.expectancy:+.2f}  "
        f"OOS exp={sp.out_sample.expectancy:+.2f}  "
        f"ratio={ratio_str}  [{flag}]"
    )


def _print_walk(label: str, wf: object) -> None:
    from backtester.validation.walkforward import WalkForwardResult
    assert isinstance(wf, WalkForwardResult)
    exps = [f"{w.expectancy:+.2f}" for w in wf.windows]
    print(
        f"  {label:35s} | window_exp=[{', '.join(exps)}]  "
        f"pct_pos={wf.pct_windows_positive:.0%}"
    )


def main() -> None:
    print(f"\n{APP_NAME} — Validation demo\n{'─' * 70}")

    # ── Scenario 1: consistent edge ──────────────────────────────────────────
    print("\nScenario 1: consistent edge (edge profile, 300 trades)")
    edge_trades = generate_trades(n_trades=300, profile="edge", seed=42)
    edge_loaded = _load_via_csv(edge_trades)
    edge_sp = in_out_split(edge_loaded)
    edge_wf = walk_forward(edge_loaded, n_windows=5)
    _print_split("IS/OOS split (30% OOS)", edge_sp)
    _print_walk("Walk-forward (5 windows)", edge_wf)

    # ── Scenario 2: decaying series ──────────────────────────────────────────
    # 300 edge (Jan–Jul 2024) + 100 negative (Aug–Dec 2024) → IS=70%=280 trades,
    # all early so IS is dominated by the edge block; OOS contains mostly negative.
    print("\nScenario 2: decaying series (300 edge → 100 negative, 30% OOS)")
    early = generate_trades(
        n_trades=300, profile="edge", seed=1,
        start_date=datetime(2024, 1, 2).date(),
        start_id=1,
    )
    late = generate_trades(
        n_trades=100, profile="negative", seed=2,
        start_date=datetime(2024, 8, 1).date(),
        start_id=301,                          # non-overlapping IDs
    )
    decay_trades = sorted(early + late, key=lambda t: t.exit_time)
    decay_sp = in_out_split(decay_trades)
    decay_wf = walk_forward(decay_trades, n_windows=6)
    _print_split("IS/OOS split (30% OOS)", decay_sp)
    _print_walk("Walk-forward (6 windows)", decay_wf)

    # ── Write full report with the decaying series ───────────────────────────
    decay_metrics = compute_metrics(decay_trades)
    decay_bs = run_bootstrap(decay_trades, n_iterations=3_000, seed=42)
    decay_sh = run_shuffle(decay_trades, n_iterations=3_000, seed=42)

    report_path = REPORTS_DIR / "sample_report.html"
    write_report(
        decay_metrics,
        report_path,
        meta={
            "Scenario": "decaying (300 edge → 100 negative)",
            "Trades": str(len(decay_trades)),
            "Generated at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        bootstrap=decay_bs,
        shuffle=decay_sh,
        split=decay_sp,
        walk=decay_wf,
    )
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
