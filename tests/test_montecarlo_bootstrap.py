from __future__ import annotations

from datetime import datetime

import pytest

from backtester.ingest.models import Trade
from backtester.ingest.synthetic import generate_trades
from backtester.metrics.core import compute_metrics
from backtester.montecarlo.bootstrap import run_bootstrap
from backtester.timeutils import to_et

_N_ITER = 2_000   # fast enough for CI, sufficient for stable percentiles


def _dt(s: str) -> datetime:
    return to_et(datetime.strptime(s, "%Y-%m-%d %H:%M"))


def _make_trade(trade_id: int, pnl: float) -> Trade:
    return Trade(
        trade_id=trade_id,
        direction="long",
        entry_time=_dt("2024-01-02 09:30"),
        entry_price=5000.0,
        exit_time=_dt("2024-01-02 10:00"),
        exit_price=5001.0,
        qty=1,
        pnl=pnl,
    )


def test_determinism() -> None:
    trades = generate_trades(n_trades=100, seed=1)
    a = run_bootstrap(trades, n_iterations=_N_ITER, seed=42)
    b = run_bootstrap(trades, n_iterations=_N_ITER, seed=42)
    assert a.expectancy_dist == b.expectancy_dist
    assert a.expectancy_ci == b.expectancy_ci


def test_different_seeds_differ() -> None:
    trades = generate_trades(n_trades=100, seed=1)
    a = run_bootstrap(trades, n_iterations=_N_ITER, seed=1)
    b = run_bootstrap(trades, n_iterations=_N_ITER, seed=2)
    assert a.expectancy_dist != b.expectancy_dist


def test_ci_ordering_all_metrics() -> None:
    """lo <= point is NOT guaranteed by percentile CI, but lo <= hi always must hold."""
    trades = generate_trades(n_trades=200, seed=7)
    r = run_bootstrap(trades, n_iterations=_N_ITER, seed=0)
    for name, ci in [
        ("expectancy", r.expectancy_ci),
        ("net_profit", r.net_profit_ci),
        ("profit_factor", r.profit_factor_ci),
        ("win_rate", r.win_rate_ci),
    ]:
        lo, hi = ci
        assert lo <= hi, f"{name} CI: lo={lo} > hi={hi}"


def test_point_estimates_match_full_sample() -> None:
    trades = generate_trades(n_trades=150, seed=3)
    m = compute_metrics(trades)
    r = run_bootstrap(trades, n_iterations=_N_ITER, seed=0)
    assert abs(r.expectancy_point - m.expectancy) < 1e-9
    assert abs(r.net_profit_point - m.net_profit) < 1e-9
    assert abs(r.win_rate_point - m.win_rate) < 1e-9


def test_dist_length_matches_n_iterations() -> None:
    trades = generate_trades(n_trades=50, seed=0)
    r = run_bootstrap(trades, n_iterations=300, seed=0)
    assert len(r.expectancy_dist) == 300


def test_edge_ci_lower_bound_positive() -> None:
    """
    Core discrimination test: a 500-trade edge profile with a genuine positive
    expectancy should have a 95% CI lower bound > 0.
    """
    trades = generate_trades(n_trades=500, profile="edge", seed=42)
    r = run_bootstrap(trades, n_iterations=_N_ITER, seed=42)
    lo, hi = r.expectancy_ci
    assert lo > 0, (
        f"Edge profile CI lower bound should be > 0, got [{lo:.4f}, {hi:.4f}]"
    )


def test_noise_ci_brackets_zero() -> None:
    """
    Core discrimination test: a 500-trade noise profile with zero commission
    (symmetric wins/losses) should have a 95% CI that brackets 0 (lo < 0 < hi).
    """
    trades = generate_trades(
        n_trades=500, profile="noise", seed=42, commission_per_contract=0.0
    )
    r = run_bootstrap(trades, n_iterations=_N_ITER, seed=42)
    lo, hi = r.expectancy_ci
    assert lo < 0 < hi, (
        f"Noise CI should bracket 0, got [{lo:.4f}, {hi:.4f}]"
    )


def test_infinite_pf_counted_not_crashed() -> None:
    """All-win trades produce infinite PF; n_inf_pf should count them without error."""
    trades = [_make_trade(i, 10.0) for i in range(1, 11)]   # all wins
    r = run_bootstrap(trades, n_iterations=200, seed=0)
    # Every resample is all-wins → every PF is inf
    assert r.n_inf_pf > 0
    assert r.n_inf_pf <= 200


def test_mixed_inf_pf_partial_count() -> None:
    """Mix of wins and losses: some resamples may be all-wins; n_inf_pf >= 0."""
    trades = [_make_trade(i, 50.0 if i % 3 != 0 else -20.0) for i in range(1, 21)]
    r = run_bootstrap(trades, n_iterations=500, seed=0)
    assert 0 <= r.n_inf_pf <= 500


def test_empty_trades_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        run_bootstrap([], n_iterations=10, seed=0)


def test_invalid_ci_level_raises() -> None:
    trades = generate_trades(n_trades=20, seed=0)
    with pytest.raises(ValueError, match="ci_level"):
        run_bootstrap(trades, ci_level=0.80)
