"""Serialize ValidationResult to a JSON-safe dict (summary fields only).

Distribution arrays (max_drawdown_dist, random_net_dist, expectancy_dist) are
intentionally excluded — they are large (n_iterations floats) and the caller can
reconstruct visualisations from the percentile summaries.
"""
from __future__ import annotations

import math
from typing import Any

from engine.metrics.core import Metrics
from engine.montecarlo.bootstrap import BootstrapResult
from engine.montecarlo.shuffle import ShuffleResult
from engine.orchestrator import ValidationResult
from engine.validation.benchmarks import BuyHoldResult, RandomEntryResult
from engine.validation.regimes import RegimeBreakdown
from engine.validation.splits import SplitResult
from engine.validation.walkforward import WalkForwardResult


def _f(v: float) -> float | None:
    """Return v if finite, else None — inf and nan are not JSON-serializable."""
    return v if math.isfinite(v) else None


def _metrics(m: Metrics) -> dict[str, Any]:
    return {
        "total_trades": m.total_trades,
        "wins": m.wins,
        "losses": m.losses,
        "win_rate": m.win_rate,
        "net_profit": m.net_profit,
        "gross_profit": m.gross_profit,
        "gross_loss": m.gross_loss,
        "avg_win": m.avg_win,
        "avg_loss": m.avg_loss,
        "expectancy": m.expectancy,
        "profit_factor": _f(m.profit_factor),
        "payoff_ratio": _f(m.payoff_ratio),
        "max_drawdown": m.max_drawdown,
        "longest_win_streak": m.longest_win_streak,
        "longest_loss_streak": m.longest_loss_streak,
        "equity_curve": m.equity_curve,
    }


def _shuffle(sh: ShuffleResult) -> dict[str, Any]:
    return {
        "n_iterations": sh.n_iterations,
        "net_profit": sh.net_profit,
        "risk_of_ruin": sh.risk_of_ruin,
        "ruin_threshold": sh.ruin_threshold,
        "max_drawdown_pctiles": {str(k): v for k, v in sh.max_drawdown_pctiles.items()},
    }


def _bootstrap(bs: BootstrapResult) -> dict[str, Any]:
    return {
        "n_iterations": bs.n_iterations,
        "ci_level": bs.ci_level,
        "expectancy_point": bs.expectancy_point,
        "expectancy_ci": list(bs.expectancy_ci),
        "net_profit_point": bs.net_profit_point,
        "net_profit_ci": list(bs.net_profit_ci),
        "win_rate_point": bs.win_rate_point,
        "win_rate_ci": list(bs.win_rate_ci),
        "profit_factor_point": _f(bs.profit_factor_point),
        "profit_factor_ci": [_f(bs.profit_factor_ci[0]), _f(bs.profit_factor_ci[1])],
        "n_inf_pf": bs.n_inf_pf,
    }


def _split(sp: SplitResult) -> dict[str, Any]:
    return {
        "oos_fraction": sp.oos_fraction,
        "split_time": sp.split_time.isoformat(),
        "is_trades": sp.in_sample.total_trades,
        "oos_trades": sp.out_sample.total_trades,
        "is_expectancy": sp.in_sample.expectancy,
        "oos_expectancy": sp.out_sample.expectancy,
        "is_net_profit": sp.in_sample.net_profit,
        "oos_net_profit": sp.out_sample.net_profit,
        "is_win_rate": sp.in_sample.win_rate,
        "oos_win_rate": sp.out_sample.win_rate,
        "edge_decayed": sp.edge_decayed,
        "expectancy_ratio": _f(sp.expectancy_ratio),
    }


def _walkforward(wf: WalkForwardResult) -> dict[str, Any]:
    return {
        "n_windows": wf.n_windows,
        "scheme": wf.scheme,
        "pct_windows_positive": wf.pct_windows_positive,
        "expectancy_mean": wf.expectancy_mean,
        "expectancy_std": wf.expectancy_std,
        "windows": [
            {
                "index": w.index,
                "start_time": w.start_time.isoformat(),
                "end_time": w.end_time.isoformat(),
                "n_trades": w.n_trades,
                "expectancy": w.expectancy,
                "net_profit": w.net_profit,
                "win_rate": w.win_rate,
                "profit_factor": _f(w.profit_factor),
                "max_drawdown": w.max_drawdown,
            }
            for w in wf.windows
        ],
    }


def _buyhold(bh: BuyHoldResult) -> dict[str, Any]:
    return {
        "strategy_net": bh.strategy_net,
        "buy_hold_net": bh.buy_hold_net,
        "beats_buy_hold": bh.beats_buy_hold,
        "start_price": bh.start_price,
        "end_price": bh.end_price,
        "start_time": bh.start_time.isoformat(),
        "end_time": bh.end_time.isoformat(),
        "instrument_symbol": bh.instrument_symbol,
    }


def _random_entry(re: RandomEntryResult) -> dict[str, Any]:
    return {
        "n_iterations": re.n_iterations,
        "n_trades": re.n_trades,
        "long_fraction": re.long_fraction,
        "strategy_net": re.strategy_net,
        "strategy_expectancy": re.strategy_expectancy,
        "net_percentile_rank": re.net_percentile_rank,
        "threshold": re.threshold,
        "beats_random": re.beats_random,
        "random_net_pctiles": {str(k): v for k, v in re.random_net_pctiles.items()},
    }


def _regime(rb: RegimeBreakdown) -> dict[str, Any]:
    return {
        "scheme": rb.scheme,
        "params": rb.params,
        "trade_counts": rb.trade_counts,
        "per_regime": {
            label: {
                "total_trades": m.total_trades,
                "win_rate": m.win_rate,
                "expectancy": m.expectancy,
                "net_profit": m.net_profit,
                "profit_factor": _f(m.profit_factor),
            }
            for label, m in rb.per_regime.items()
        },
    }


def serialize_result(result: ValidationResult) -> dict[str, Any]:
    """Convert a ValidationResult to a JSON-serializable dict (summary fields only)."""
    return {
        "metrics": _metrics(result.metrics),
        "shuffle": _shuffle(result.shuffle),
        "bootstrap": _bootstrap(result.bootstrap),
        "split": _split(result.split) if result.split else None,
        "walk_forward": _walkforward(result.walk_forward) if result.walk_forward else None,
        "buy_hold": _buyhold(result.buy_hold) if result.buy_hold else None,
        "random_entry": _random_entry(result.random_entry) if result.random_entry else None,
        "regimes": {k: _regime(v) for k, v in result.regimes.items()},
        "skipped": result.skipped,
    }
