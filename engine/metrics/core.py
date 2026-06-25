from __future__ import annotations

from dataclasses import dataclass

from engine.ingest.models import Trade


@dataclass(frozen=True)
class Metrics:
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    avg_win: float
    avg_loss: float
    expectancy: float
    profit_factor: float
    payoff_ratio: float
    max_drawdown: float
    longest_win_streak: int
    longest_loss_streak: int
    equity_curve: list[float]   # cumulative net P&L after each trade


def compute_metrics(trades: list[Trade]) -> Metrics:
    """Compute core KPIs from a list of trades. Pure function — no side effects."""
    if not trades:
        return Metrics(
            total_trades=0, wins=0, losses=0, win_rate=0.0,
            gross_profit=0.0, gross_loss=0.0, net_profit=0.0,
            avg_win=0.0, avg_loss=0.0, expectancy=0.0,
            profit_factor=0.0, payoff_ratio=0.0, max_drawdown=0.0,
            longest_win_streak=0, longest_loss_streak=0,
            equity_curve=[],
        )

    win_pnls: list[float] = []
    loss_pnls: list[float] = []
    equity_curve: list[float] = []
    cumulative = 0.0

    for t in trades:
        cumulative = round(cumulative + t.pnl, 10)
        equity_curve.append(cumulative)
        if t.pnl > 0:
            win_pnls.append(t.pnl)
        else:
            loss_pnls.append(t.pnl)

    wins = len(win_pnls)
    losses = len(loss_pnls)
    total = len(trades)

    gross_profit = sum(win_pnls)
    gross_loss = sum(loss_pnls)          # negative number
    net_profit = gross_profit + gross_loss

    win_rate = wins / total
    avg_win = gross_profit / wins if wins else 0.0
    avg_loss = gross_loss / losses if losses else 0.0   # negative

    # Expectancy: average P&L per trade
    expectancy = net_profit / total

    # Profit factor: gross profit / |gross loss|; infinite when no losses
    abs_loss = abs(gross_loss)
    profit_factor = gross_profit / abs_loss if abs_loss else float("inf")

    # Payoff ratio: avg win / |avg loss|
    abs_avg_loss = abs(avg_loss)
    payoff_ratio = avg_win / abs_avg_loss if abs_avg_loss else float("inf")

    # Max drawdown: peak-to-trough on equity curve (USD)
    peak = equity_curve[0]
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd

    # Streak calculation
    longest_win_streak = 0
    longest_loss_streak = 0
    cur_win = 0
    cur_loss = 0
    for t in trades:
        if t.pnl > 0:
            cur_win += 1
            cur_loss = 0
        else:
            cur_loss += 1
            cur_win = 0
        longest_win_streak = max(longest_win_streak, cur_win)
        longest_loss_streak = max(longest_loss_streak, cur_loss)

    return Metrics(
        total_trades=total,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        net_profit=net_profit,
        avg_win=avg_win,
        avg_loss=avg_loss,
        expectancy=expectancy,
        profit_factor=profit_factor,
        payoff_ratio=payoff_ratio,
        max_drawdown=max_dd,
        longest_win_streak=longest_win_streak,
        longest_loss_streak=longest_loss_streak,
        equity_curve=equity_curve,
    )
