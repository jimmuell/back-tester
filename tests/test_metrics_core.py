from __future__ import annotations

from datetime import datetime

from engine.ingest.models import Trade
from engine.metrics.core import compute_metrics
from engine.timeutils import to_et


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


# Hand-constructed 4-trade list with known outcomes:
#   Trade 1: +100.00  (win)
#   Trade 2:  -40.00  (loss)
#   Trade 3:  +60.00  (win)
#   Trade 4:  -20.00  (loss)
#
# wins=2, losses=2, total=4
# win_rate = 2/4 = 0.50
# gross_profit = 100 + 60 = 160.00
# gross_loss   = -40 + -20 = -60.00
# net_profit   = 160 - 60 = 100.00
# avg_win      = 160 / 2 = 80.00
# avg_loss     = -60 / 2 = -30.00
# expectancy   = 100 / 4 = 25.00
# profit_factor = 160 / 60 ≈ 2.6667
# payoff_ratio  = 80 / 30 ≈ 2.6667
#
# equity_curve = [100, 60, 120, 100]
# max_drawdown: peak=120, trough after = 100 → dd = 20.00
#               also: peak=100, trough=60 → dd = 40.00
#               → max_drawdown = 40.00
#
# longest_win_streak = 1 (no consecutive wins: W L W L)
# longest_loss_streak = 1

KNOWN_TRADES = [
    _make_trade(1, 100.0),
    _make_trade(2, -40.0),
    _make_trade(3, 60.0),
    _make_trade(4, -20.0),
]


def test_win_rate() -> None:
    m = compute_metrics(KNOWN_TRADES)
    assert m.win_rate == 0.5


def test_net_profit() -> None:
    m = compute_metrics(KNOWN_TRADES)
    assert abs(m.net_profit - 100.0) < 1e-6


def test_expectancy() -> None:
    m = compute_metrics(KNOWN_TRADES)
    assert abs(m.expectancy - 25.0) < 1e-6


def test_profit_factor() -> None:
    m = compute_metrics(KNOWN_TRADES)
    assert abs(m.profit_factor - (160.0 / 60.0)) < 1e-6


def test_max_drawdown() -> None:
    # equity = [100, 60, 120, 100]
    # peak after trade 1 = 100 → dd at trade 2 = 40
    # peak after trade 3 = 120 → dd at trade 4 = 20
    # → max_drawdown = 40
    m = compute_metrics(KNOWN_TRADES)
    assert abs(m.max_drawdown - 40.0) < 1e-6


def test_equity_curve_length() -> None:
    m = compute_metrics(KNOWN_TRADES)
    assert len(m.equity_curve) == 4


def test_equity_curve_values() -> None:
    m = compute_metrics(KNOWN_TRADES)
    expected = [100.0, 60.0, 120.0, 100.0]
    for a, b in zip(m.equity_curve, expected):
        assert abs(a - b) < 1e-6


def test_streaks() -> None:
    m = compute_metrics(KNOWN_TRADES)
    assert m.longest_win_streak == 1
    assert m.longest_loss_streak == 1


def test_consecutive_wins_streak() -> None:
    trades = [_make_trade(i, 10.0) for i in range(1, 6)]
    m = compute_metrics(trades)
    assert m.longest_win_streak == 5
    assert m.longest_loss_streak == 0


def test_empty_trades() -> None:
    m = compute_metrics([])
    assert m.total_trades == 0
    assert m.net_profit == 0.0
    assert m.equity_curve == []


def test_no_losses() -> None:
    trades = [_make_trade(i, 50.0) for i in range(1, 4)]
    m = compute_metrics(trades)
    assert m.profit_factor == float("inf")
    assert m.win_rate == 1.0
    assert m.max_drawdown == 0.0
