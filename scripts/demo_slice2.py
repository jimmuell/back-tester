"""Slice 2 demo: edge vs noise — bootstrap CIs + shuffle drawdown distribution."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from engine.config import APP_NAME
from engine.ingest.synthetic import generate_trades, write_tradingview_csv
from engine.ingest.tradingview import load_trades
from engine.metrics.core import compute_metrics
from engine.montecarlo.bootstrap import run_bootstrap
from engine.montecarlo.shuffle import run_shuffle
from engine.report.html import write_report

REPORTS_DIR = Path(__file__).parent.parent / "reports"


def _run_profile(
    label: str,
    profile: str,
    seed: int,
    n_trades: int = 300,
    commission: float = 1.24,
) -> None:
    import tempfile

    trades = generate_trades(
        n_trades=n_trades,
        profile=profile,  # type: ignore[arg-type]
        seed=seed,
        commission_per_contract=commission,
    )
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = Path(f.name)
    write_tradingview_csv(trades, csv_path)
    loaded = load_trades(csv_path)
    csv_path.unlink(missing_ok=True)

    metrics = compute_metrics(loaded)
    bs = run_bootstrap(loaded, n_iterations=5_000, seed=seed)
    sh = run_shuffle(loaded, n_iterations=5_000, seed=seed)

    lo, hi = bs.expectancy_ci
    ci_pct = f"{int(bs.ci_level * 100)}%"
    print(
        f"  {label:30s} | expectancy={bs.expectancy_point:+.2f}  "
        f"{ci_pct} CI [{lo:+.2f}, {hi:+.2f}]  "
        f"risk_of_ruin={sh.risk_of_ruin:.1%}"
    )

    report_path = REPORTS_DIR / f"sample_report_{profile}.html"
    meta = {
        "Profile": profile,
        "Seed": str(seed),
        "Trades": str(n_trades),
        "MC iterations": "5,000",
        "Generated at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    write_report(
        metrics,
        report_path,
        meta=meta,
        bootstrap=bs,
        shuffle=sh,
    )
    print(f"  {'':30s}   Report: {report_path}")


def main() -> None:
    print(f"\n{APP_NAME} — Slice 2 demo (Monte Carlo)\n{'─' * 60}")

    # Edge: genuine positive expectancy
    _run_profile("Edge profile (seed=42)", profile="edge", seed=42)

    # Noise: zero-commission, symmetric — CI should bracket 0
    _run_profile(
        "Noise profile, 0 commission",
        profile="noise",
        seed=42,
        commission=0.0,
    )

    # Also write the fuller report as the primary sample
    print(f"\nPrimary report (edge, with MC): {REPORTS_DIR / 'sample_report.html'}")
    import tempfile
    trades = generate_trades(n_trades=300, profile="edge", seed=42)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        csv_path = Path(f.name)
    write_tradingview_csv(trades, csv_path)
    loaded = load_trades(csv_path)
    csv_path.unlink(missing_ok=True)

    metrics = compute_metrics(loaded)
    bs = run_bootstrap(loaded, n_iterations=5_000, seed=42)
    sh = run_shuffle(loaded, n_iterations=5_000, seed=42)
    write_report(
        metrics,
        REPORTS_DIR / "sample_report.html",
        meta={"Profile": "edge", "Seed": "42", "Trades": "300", "MC iterations": "5,000"},
        bootstrap=bs,
        shuffle=sh,
    )


if __name__ == "__main__":
    main()
