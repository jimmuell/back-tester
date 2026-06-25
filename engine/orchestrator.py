"""Validation orchestrator — single entry point that runs all validation passes."""
from __future__ import annotations

from dataclasses import dataclass

from engine.ingest.firstrate import BarSet
from engine.ingest.models import Trade
from engine.instruments import MES, Instrument
from engine.metrics.core import Metrics, compute_metrics
from engine.montecarlo.bootstrap import BootstrapResult, run_bootstrap
from engine.montecarlo.shuffle import ShuffleResult, run_shuffle
from engine.validation.benchmarks import (
    BuyHoldResult,
    RandomEntryResult,
    buy_and_hold,
    random_entry,
)
from engine.validation.regimes import RegimeBreakdown, regime_breakdown
from engine.validation.splits import SplitResult, in_out_split
from engine.validation.walkforward import WalkForwardResult, walk_forward


@dataclass(frozen=True)
class ValidationConfig:
    seed: int = 42
    mc_iterations: int = 10_000
    bootstrap_ci_level: float = 0.95
    ruin_threshold: float | None = None
    oos_fraction: float = 0.30
    n_windows: int = 5
    random_entry_iterations: int = 10_000
    random_entry_threshold: float = 0.95
    regime_schemes: tuple[str, ...] = ("trend", "volatility")
    ma_length: int = 50
    vol_length: int = 20
    high_vol_quantile: float = 0.67
    instrument: Instrument = MES
    qty: int = 1


@dataclass(frozen=True)
class ValidationResult:
    metrics: Metrics
    shuffle: ShuffleResult
    bootstrap: BootstrapResult
    split: SplitResult | None
    walk_forward: WalkForwardResult | None
    buy_hold: BuyHoldResult | None
    random_entry: RandomEntryResult | None
    regimes: dict[str, RegimeBreakdown]
    skipped: list[str]
    config: ValidationConfig


def validate(
    trades: list[Trade],
    bars: BarSet | None = None,
    *,
    config: ValidationConfig = ValidationConfig(),
) -> ValidationResult:
    """Run all validation passes and return a unified result.

    Always runs: compute_metrics, run_shuffle, run_bootstrap.
    Conditionally runs: in_out_split, walk_forward (guard on trade count).
    Only with bars: buy_and_hold, random_entry, regime_breakdown per scheme.
    Any skipped pass is recorded in result.skipped with a reason.

    Raises ValueError for an empty trade list.
    """
    if not trades:
        raise ValueError("trades list is empty — nothing to validate")

    skipped: list[str] = []

    metrics = compute_metrics(trades)
    shuffle = run_shuffle(
        trades,
        n_iterations=config.mc_iterations,
        seed=config.seed,
        ruin_threshold=config.ruin_threshold,
    )
    bootstrap = run_bootstrap(
        trades,
        n_iterations=config.mc_iterations,
        seed=config.seed,
        ci_level=config.bootstrap_ci_level,
    )

    split: SplitResult | None = None
    try:
        split = in_out_split(trades, oos_fraction=config.oos_fraction)
    except ValueError as exc:
        skipped.append(f"split: {exc}")

    wf: WalkForwardResult | None = None
    try:
        wf = walk_forward(trades, n_windows=config.n_windows)
    except ValueError as exc:
        skipped.append(f"walk_forward: {exc}")

    bh: BuyHoldResult | None = None
    re: RandomEntryResult | None = None
    regimes: dict[str, RegimeBreakdown] = {}

    if bars is not None:
        try:
            bh = buy_and_hold(trades, bars, instrument=config.instrument, qty=config.qty)
        except Exception as exc:
            skipped.append(f"buy_hold: {exc}")

        try:
            re = random_entry(
                trades,
                bars,
                n_iterations=config.random_entry_iterations,
                seed=config.seed,
                instrument=config.instrument,
                qty=config.qty,
                threshold=config.random_entry_threshold,
            )
        except Exception as exc:
            skipped.append(f"random_entry: {exc}")

        for scheme in config.regime_schemes:
            try:
                rb = regime_breakdown(
                    trades,
                    bars,
                    scheme=scheme,  # type: ignore[arg-type]
                    ma_length=float(config.ma_length),
                    vol_length=float(config.vol_length),
                    high_vol_quantile=config.high_vol_quantile,
                )
                regimes[scheme] = rb
            except Exception as exc:
                skipped.append(f"regime[{scheme}]: {exc}")
    else:
        skipped.append("buy_hold: bars not provided")
        skipped.append("random_entry: bars not provided")
        for scheme in config.regime_schemes:
            skipped.append(f"regime[{scheme}]: bars not provided")

    return ValidationResult(
        metrics=metrics,
        shuffle=shuffle,
        bootstrap=bootstrap,
        split=split,
        walk_forward=wf,
        buy_hold=bh,
        random_entry=re,
        regimes=regimes,
        skipped=skipped,
        config=config,
    )
