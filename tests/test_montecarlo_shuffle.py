from __future__ import annotations

from datetime import datetime

import pytest

from engine.ingest.models import Trade
from engine.metrics.core import compute_metrics
from engine.montecarlo.shuffle import run_shuffle
from engine.timeutils import to_et

_N_ITER = 500   # fast for tests


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


def _edge_trades(n: int = 100) -> list[Trade]:
    from engine.ingest.synthetic import generate_trades
    return generate_trades(n_trades=n, profile="edge", seed=7)


def test_determinism() -> None:
    trades = _edge_trades()
    a = run_shuffle(trades, n_iterations=_N_ITER, seed=1)
    b = run_shuffle(trades, n_iterations=_N_ITER, seed=1)
    assert a.max_drawdown_dist == b.max_drawdown_dist
    assert a.longest_loss_streak_dist == b.longest_loss_streak_dist


def test_different_seeds_differ() -> None:
    trades = _edge_trades()
    a = run_shuffle(trades, n_iterations=_N_ITER, seed=1)
    b = run_shuffle(trades, n_iterations=_N_ITER, seed=2)
    assert a.max_drawdown_dist != b.max_drawdown_dist


def test_net_profit_invariant_across_seeds() -> None:
    """Net P&L must equal sum(pnl) regardless of seed or iterations — it's the same trades."""
    trades = _edge_trades()
    expected = sum(t.pnl for t in trades)
    for seed in (1, 42, 99):
        result = run_shuffle(trades, n_iterations=100, seed=seed)
        assert abs(result.net_profit - expected) < 1e-6, (
            f"seed={seed}: net_profit {result.net_profit} != {expected}"
        )


def test_net_profit_equals_sum_pnl() -> None:
    trades = [_make_trade(i, float(i * 10 - 30)) for i in range(1, 9)]
    result = run_shuffle(trades, n_iterations=200, seed=0)
    assert abs(result.net_profit - sum(t.pnl for t in trades)) < 1e-6


def test_dist_length_matches_n_iterations() -> None:
    trades = _edge_trades()
    result = run_shuffle(trades, n_iterations=300, seed=0)
    assert len(result.max_drawdown_dist) == 300
    assert len(result.longest_loss_streak_dist) == 300


def test_percentiles_non_decreasing() -> None:
    trades = _edge_trades()
    result = run_shuffle(trades, n_iterations=_N_ITER, seed=0)
    p = result.max_drawdown_pctiles
    keys = sorted(p)
    for a, b in zip(keys, keys[1:]):
        assert p[a] <= p[b], f"percentile {a} > {b}: {p[a]} > {p[b]}"


def test_risk_of_ruin_in_unit_interval() -> None:
    trades = _edge_trades()
    result = run_shuffle(trades, n_iterations=_N_ITER, seed=0)
    assert 0.0 <= result.risk_of_ruin <= 1.0


def test_observed_drawdown_within_distribution() -> None:
    """The original-order max drawdown must lie within [min, max] of the shuffle dist."""
    trades = _edge_trades()
    observed_dd = compute_metrics(trades).max_drawdown
    result = run_shuffle(trades, n_iterations=_N_ITER, seed=0)
    assert min(result.max_drawdown_dist) <= observed_dd <= max(result.max_drawdown_dist), (
        f"observed_dd={observed_dd} outside [{min(result.max_drawdown_dist)}, "
        f"{max(result.max_drawdown_dist)}]"
    )


def test_custom_ruin_threshold() -> None:
    trades = _edge_trades()
    threshold = 100.0
    result = run_shuffle(trades, n_iterations=_N_ITER, seed=0, ruin_threshold=threshold)
    assert result.ruin_threshold == threshold
    # Manual check: fraction of dist >= threshold
    manual = sum(1 for dd in result.max_drawdown_dist if dd >= threshold) / _N_ITER
    assert abs(result.risk_of_ruin - manual) < 1e-9


def test_empty_trades_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        run_shuffle([], n_iterations=10, seed=0)


def test_percentile_keys() -> None:
    trades = _edge_trades()
    result = run_shuffle(trades, n_iterations=100, seed=0)
    assert set(result.max_drawdown_pctiles.keys()) == {5, 25, 50, 75, 95}
