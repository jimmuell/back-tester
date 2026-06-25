from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

import backtester.orchestrator as _orch
from backtester import ValidationConfig, validate
from backtester.ingest.models import Trade
from backtester.ingest.synthetic import generate_bars, generate_trades
from backtester.instruments import ES, MES

# ── Helpers ───────────────────────────────────────────────────────────────────

def _bar_trades(n: int = 60, hold: int = 5, seed: int = 7) -> tuple[list[Trade], object]:
    """Return (trades, bars) where trades are bar-consistent (timestamps from bars)."""
    import numpy as np
    bars = generate_bars(n_bars=200, seed=42, drift=0.003, daily_vol=0.008)
    closes = bars.df["close"].to_numpy()
    timestamps = bars.df.index
    last_bar = len(closes) - 1

    rng = np.random.default_rng(seed)
    entry_idxs = rng.integers(0, last_bar - hold, size=n)
    is_long = rng.random(size=n) < 0.5

    trades = []
    for tid, (ei, long) in enumerate(zip(entry_idxs.tolist(), is_long.tolist()), 1):
        ei = int(ei)
        xi = min(ei + hold, last_bar)
        direction = "long" if long else "short"
        dir_sign = 1 if long else -1
        pnl = dir_sign * (closes[xi] - closes[ei]) * MES.point_value
        trades.append(Trade(
            trade_id=tid, direction=direction,
            entry_time=timestamps[ei].to_pydatetime(),
            exit_time=timestamps[xi].to_pydatetime(),
            entry_price=float(closes[ei]),
            exit_price=float(closes[xi]),
            qty=1, pnl=pnl,
        ))
    return trades, bars


# ── ValidationConfig ──────────────────────────────────────────────────────────

def test_config_defaults() -> None:
    cfg = ValidationConfig()
    assert cfg.seed == 42
    assert cfg.mc_iterations == 10_000
    assert cfg.bootstrap_ci_level == 0.95
    assert cfg.ruin_threshold is None
    assert cfg.oos_fraction == 0.30
    assert cfg.n_windows == 5
    assert cfg.random_entry_iterations == 10_000
    assert cfg.random_entry_threshold == 0.95
    assert cfg.regime_schemes == ("trend", "volatility")
    assert cfg.ma_length == 50
    assert cfg.vol_length == 20
    assert cfg.high_vol_quantile == 0.67
    assert cfg.instrument == MES
    assert cfg.qty == 1


def test_config_custom_instrument() -> None:
    cfg = ValidationConfig(instrument=ES)
    assert cfg.instrument == ES


def test_config_frozen() -> None:
    cfg = ValidationConfig()
    with pytest.raises(Exception):
        cfg.seed = 99  # type: ignore[misc]


# ── validate() — empty trades guard ──────────────────────────────────────────

def test_validate_raises_on_empty_trades() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate([])


# ── validate() — no bars ──────────────────────────────────────────────────────

def test_validate_no_bars_always_runs_core() -> None:
    trades = generate_trades(n_trades=30, seed=42)
    result = validate(trades, config=ValidationConfig(mc_iterations=500))
    assert result.metrics.total_trades == 30
    assert result.shuffle is not None
    assert result.bootstrap is not None


def test_validate_no_bars_skips_bar_analyses() -> None:
    trades = generate_trades(n_trades=30, seed=42)
    result = validate(trades, config=ValidationConfig(mc_iterations=500))
    assert result.buy_hold is None
    assert result.random_entry is None
    assert result.regimes == {}
    assert any("bars not provided" in s for s in result.skipped)


def test_validate_no_bars_skipped_has_entries_for_all_regimes() -> None:
    trades = generate_trades(n_trades=30, seed=42)
    cfg = ValidationConfig(mc_iterations=500, regime_schemes=("trend", "volatility"))
    result = validate(trades, config=cfg)
    skipped_keys = [s.split(":")[0] for s in result.skipped]
    assert "regime[trend]" in skipped_keys
    assert "regime[volatility]" in skipped_keys


# ── validate() — with bars ────────────────────────────────────────────────────

def test_validate_with_bars_populates_all_fields() -> None:
    trades, bars = _bar_trades(n=60)
    cfg = ValidationConfig(mc_iterations=500, random_entry_iterations=500)
    result = validate(trades, bars, config=cfg)
    assert result.metrics is not None
    assert result.shuffle is not None
    assert result.bootstrap is not None
    assert result.split is not None
    assert result.walk_forward is not None
    assert result.buy_hold is not None
    assert result.random_entry is not None


def test_validate_with_bars_has_regimes_for_each_scheme() -> None:
    trades, bars = _bar_trades(n=60)
    cfg = ValidationConfig(mc_iterations=500, random_entry_iterations=500)
    result = validate(trades, bars, config=cfg)
    assert "trend" in result.regimes
    assert "volatility" in result.regimes


def test_validate_regime_trade_counts_sum_to_total() -> None:
    trades, bars = _bar_trades(n=60)
    cfg = ValidationConfig(mc_iterations=500, random_entry_iterations=500)
    result = validate(trades, bars, config=cfg)
    for scheme, rb in result.regimes.items():
        total = sum(rb.trade_counts.values())
        assert total == len(trades), f"{scheme}: {total} != {len(trades)}"


def test_validate_result_carries_config() -> None:
    trades = generate_trades(n_trades=20, seed=42)
    cfg = ValidationConfig(seed=99, mc_iterations=500)
    result = validate(trades, config=cfg)
    assert result.config.seed == 99
    assert result.config.mc_iterations == 500


# ── validate() — split/walk_forward guards ───────────────────────────────────

def test_validate_split_present_with_enough_trades() -> None:
    trades = generate_trades(n_trades=30, seed=42)
    result = validate(trades, config=ValidationConfig(mc_iterations=500))
    assert result.split is not None


def test_validate_walk_forward_present_with_enough_trades() -> None:
    trades = generate_trades(n_trades=30, seed=42)
    result = validate(trades, config=ValidationConfig(mc_iterations=500, n_windows=5))
    assert result.walk_forward is not None


def test_validate_walk_forward_skipped_when_too_few_trades() -> None:
    trades = generate_trades(n_trades=3, seed=42)
    result = validate(trades, config=ValidationConfig(mc_iterations=100, n_windows=5))
    assert result.walk_forward is None
    assert any("walk_forward" in s for s in result.skipped)


# ── validate() — skipped list ─────────────────────────────────────────────────

def test_skipped_is_list_of_strings() -> None:
    trades = generate_trades(n_trades=30, seed=42)
    result = validate(trades, config=ValidationConfig(mc_iterations=500))
    assert isinstance(result.skipped, list)
    assert all(isinstance(s, str) for s in result.skipped)


def test_validate_no_bars_skipped_length() -> None:
    trades = generate_trades(n_trades=30, seed=42)
    cfg = ValidationConfig(mc_iterations=500, regime_schemes=("trend", "volatility"))
    result = validate(trades, config=cfg)
    # buy_hold + random_entry + 2 regime schemes = 4 entries minimum
    assert len(result.skipped) >= 4


# ── Determinism ───────────────────────────────────────────────────────────────

def test_validate_deterministic() -> None:
    trades, bars = _bar_trades(n=40)
    cfg = ValidationConfig(mc_iterations=500, random_entry_iterations=500, seed=7)
    r1 = validate(trades, bars, config=cfg)
    r2 = validate(trades, bars, config=cfg)
    assert r1.metrics.net_profit == r2.metrics.net_profit
    assert r1.shuffle.risk_of_ruin == r2.shuffle.risk_of_ruin
    assert r1.bootstrap.expectancy_point == r2.bootstrap.expectancy_point
    for scheme in r1.regimes:
        assert r1.regimes[scheme].trade_counts == r2.regimes[scheme].trade_counts


# ── backtester.__init__ re-exports ────────────────────────────────────────────

def test_backtester_init_exports() -> None:
    import backtester
    assert hasattr(backtester, "validate")
    assert hasattr(backtester, "ValidationConfig")
    assert hasattr(backtester, "ValidationResult")


# ── ValidationResult structure ────────────────────────────────────────────────

def test_validation_result_is_frozen() -> None:
    trades = generate_trades(n_trades=20, seed=42)
    result = validate(trades, config=ValidationConfig(mc_iterations=200))
    with pytest.raises(Exception):
        result.skipped = []  # type: ignore[misc]


# ── BenchmarkError → skipped; real errors propagate ──────────────────────────

def test_buy_hold_skipped_on_benchmark_error() -> None:
    """Bars from 2024, trades from 2026 → BenchmarkError → buy_hold in skipped."""
    bars = generate_bars(n_bars=100, seed=42, start=date(2024, 1, 2))
    trades = generate_trades(n_trades=10, seed=42, start_date=date(2026, 1, 2))
    cfg = ValidationConfig(mc_iterations=200, random_entry_iterations=200)
    result = validate(trades, bars, config=cfg)
    assert result.metrics is not None
    assert result.shuffle is not None
    assert result.bootstrap is not None
    assert any("buy_hold" in s for s in result.skipped)


def test_regime_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """RuntimeError from regime_breakdown must not be swallowed into skipped."""
    trades, bars = _bar_trades(n=30)
    cfg = ValidationConfig(mc_iterations=200, random_entry_iterations=200)

    def _boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("injected regime error")

    with patch.object(_orch, "regime_breakdown", _boom):
        with pytest.raises(RuntimeError, match="injected regime error"):
            validate(trades, bars, config=cfg)
