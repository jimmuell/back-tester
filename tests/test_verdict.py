"""Tests for engine/verdict.py — honest interpretation layer.

Uses validate() on generated edge/noise/decaying trade lists to verify
that findings and overall verdicts are correctly labeled and worded.
"""
from __future__ import annotations

import pytest

from engine import ValidationConfig, validate
from engine.ingest.models import Trade
from engine.ingest.synthetic import generate_trades
from engine.verdict import Finding, Verdict, VerdictStatus, summarize

# ── Helpers ───────────────────────────────────────────────────────────────────

def _edge_result(seed: int = 42):
    """ValidationResult from a clear-edge trade list (no bars)."""
    trades = generate_trades(n_trades=300, profile="edge", seed=seed)
    cfg = ValidationConfig(seed=42, mc_iterations=2_000, random_entry_iterations=2_000)
    return validate(trades, config=cfg)


def _noise_result(seed: int = 42):
    """ValidationResult from a noise trade list (no bars)."""
    trades = generate_trades(n_trades=300, profile="noise", seed=seed)
    cfg = ValidationConfig(seed=42, mc_iterations=2_000, random_entry_iterations=2_000)
    return validate(trades, config=cfg)


def _decaying_result(seed: int = 42):
    """ValidationResult where IS expectancy is positive but OOS decays.

    Strategy: generate an IS portion with 'edge' profile and OOS with 'noise'
    profile, combined into a single chronological trade list.
    """
    from datetime import timedelta

    is_trades = generate_trades(n_trades=150, profile="edge", seed=seed)
    oos_trades = generate_trades(n_trades=150, profile="noise", seed=seed + 1)

    # Shift OOS timestamps so they come after IS
    if is_trades and oos_trades:
        last_is_exit = max(t.exit_time for t in is_trades)
        first_oos_entry = min(t.entry_time for t in oos_trades)
        shift = last_is_exit - first_oos_entry + timedelta(days=1)
        shifted_oos = []
        max_id = max(t.trade_id for t in is_trades)
        for i, t in enumerate(oos_trades, start=1):
            shifted_oos.append(Trade(
                trade_id=max_id + i,
                direction=t.direction,
                entry_time=t.entry_time + shift,
                exit_time=t.exit_time + shift,
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                qty=t.qty,
                pnl=t.pnl,
            ))
        combined = list(is_trades) + shifted_oos
    else:
        combined = list(is_trades) + list(oos_trades)

    cfg = ValidationConfig(seed=42, mc_iterations=2_000, random_entry_iterations=2_000)
    return validate(combined, config=cfg)


def _no_bars_result(seed: int = 42):
    """ValidationResult from edge trades with NO bar data supplied."""
    trades = generate_trades(n_trades=200, profile="edge", seed=seed)
    cfg = ValidationConfig(seed=42, mc_iterations=2_000, random_entry_iterations=2_000)
    return validate(trades, config=cfg)


def _finding(verdict: Verdict, key: str) -> Finding:
    for f in verdict.findings:
        if f.key == key:
            return f
    raise KeyError(f"No finding with key={key!r}")


# ── Verdict structure ─────────────────────────────────────────────────────────

def test_verdict_has_five_findings() -> None:
    result = _noise_result()
    v = summarize(result)
    assert len(v.findings) == 5


def test_verdict_finding_keys() -> None:
    result = _noise_result()
    v = summarize(result)
    keys = {f.key for f in v.findings}
    assert keys == {"edge_vs_luck", "path_risk", "persistence", "signal_vs_exposure", "vs_buy_hold"}


def test_verdict_overall_is_valid_status() -> None:
    valid: set[VerdictStatus] = {"pass", "caution", "fail", "inconclusive", "info"}
    for result_fn in [_edge_result, _noise_result]:
        v = summarize(result_fn())
        assert v.overall in valid


# ── Edge scenario ─────────────────────────────────────────────────────────────

def test_edge_verdict_has_nonempty_summary() -> None:
    v = summarize(_edge_result())
    assert len(v.summary) > 10


def test_edge_summary_never_says_confirmed_edge() -> None:
    """All-pass summary must NOT claim a confirmed edge (multiple-testing honesty)."""
    v = summarize(_edge_result())
    lowered = v.summary.lower()
    assert "confirmed edge" not in lowered or "not" in lowered or "must not" in lowered


def test_edge_summary_mentions_multiple_testing() -> None:
    v = summarize(_edge_result())
    assert "multiple" in v.summary.lower() or "testing" in v.summary.lower()


def test_edge_vs_luck_pass_has_caveat_in_detail() -> None:
    """Edge-vs-luck pass must note single-test / multiple-testing caveat in detail."""
    result = _edge_result()
    v = summarize(result)
    f = _finding(v, "edge_vs_luck")
    if f.status == "pass":
        assert "multiple" in f.detail.lower() or "single" in f.detail.lower()


def test_edge_vs_luck_stat_is_ci_lower_bound() -> None:
    result = _edge_result()
    v = summarize(result)
    f = _finding(v, "edge_vs_luck")
    lo, _hi = result.bootstrap.expectancy_ci
    assert f.stat == pytest.approx(lo)


def test_path_risk_stat_is_ror() -> None:
    result = _edge_result()
    v = summarize(result)
    f = _finding(v, "path_risk")
    assert f.stat == pytest.approx(result.shuffle.risk_of_ruin)


def test_path_risk_is_info_or_caution() -> None:
    result = _edge_result()
    v = summarize(result)
    f = _finding(v, "path_risk")
    assert f.status in ("info", "caution")


def test_path_risk_detail_clarifies_not_account_ruin() -> None:
    result = _edge_result()
    v = summarize(result)
    f = _finding(v, "path_risk")
    assert "not" in f.detail.lower() or "NOT" in f.detail


def test_vs_buy_hold_always_info_no_bars() -> None:
    result = _no_bars_result()
    v = summarize(result)
    f = _finding(v, "vs_buy_hold")
    assert f.status == "info"


# ── Noise scenario ────────────────────────────────────────────────────────────

def test_noise_overall_is_not_pass() -> None:
    result = _noise_result()
    v = summarize(result)
    assert v.overall != "pass"


def test_noise_edge_vs_luck_not_pass() -> None:
    result = _noise_result()
    v = summarize(result)
    f = _finding(v, "edge_vs_luck")
    assert f.status in ("inconclusive", "fail")


# ── Decaying edge ─────────────────────────────────────────────────────────────

def test_decaying_persistence_may_fail() -> None:
    """Decaying result should ideally flag persistence as fail; at minimum it's not pass."""
    result = _decaying_result()
    v = summarize(result)
    f = _finding(v, "persistence")
    # When edge decays IS→OOS the persistence finding should be fail or at most caution.
    assert f.status in ("fail", "caution", "inconclusive")


def test_decaying_overall_is_not_pass_when_persistence_fails() -> None:
    result = _decaying_result()
    v = summarize(result)
    pf = _finding(v, "persistence")
    if pf.status == "fail":
        assert v.overall == "fail"


# ── No-bars scenario ──────────────────────────────────────────────────────────

def test_no_bars_signal_vs_exposure_inconclusive() -> None:
    result = _no_bars_result()
    v = summarize(result)
    f = _finding(v, "signal_vs_exposure")
    assert f.status == "inconclusive"


def test_no_bars_signal_detail_mentions_bar_data() -> None:
    result = _no_bars_result()
    v = summarize(result)
    f = _finding(v, "signal_vs_exposure")
    assert "bar" in f.detail.lower() or "random" in f.detail.lower()


def test_no_bars_vs_buy_hold_inconclusive_or_info() -> None:
    result = _no_bars_result()
    v = summarize(result)
    f = _finding(v, "vs_buy_hold")
    assert f.status in ("info", "inconclusive")


# ── Extreme rank caveat ───────────────────────────────────────────────────────

def test_inconclusive_signal_detail_has_extreme_rank_note() -> None:
    """When signal_vs_exposure is inconclusive (mid-range rank), detail must note extreme ranks."""
    from engine.orchestrator import ValidationResult
    from engine.validation.benchmarks import RandomEntryResult

    result = _edge_result()
    # Patch random_entry with a mid-range rank to force inconclusive
    mid_rank = 0.50
    thr = 0.95
    fake_re = RandomEntryResult(
        n_iterations=1000,
        seed=42,
        n_trades=100,
        long_fraction=0.5,
        strategy_net=100.0,
        strategy_expectancy=1.0,
        net_percentile_rank=mid_rank,
        threshold=thr,
        beats_random=False,
        random_net_pctiles={10: -500.0, 25: -200.0, 50: 0.0, 75: 200.0, 90: 500.0},
        random_net_dist=[0.0],
    )
    patched = ValidationResult(
        metrics=result.metrics,
        shuffle=result.shuffle,
        bootstrap=result.bootstrap,
        split=result.split,
        walk_forward=result.walk_forward,
        buy_hold=result.buy_hold,
        random_entry=fake_re,
        regimes=result.regimes,
        skipped=result.skipped,
        config=result.config,
    )
    v = summarize(patched)
    f = _finding(v, "signal_vs_exposure")
    assert f.status == "inconclusive"
    assert "extreme" in f.detail.lower() or "mid" in f.detail.lower()


# ── Backend serialization ─────────────────────────────────────────────────────

def test_serialize_result_has_verdict_block() -> None:
    from backend.serialization import serialize_result
    result = _noise_result()
    d = serialize_result(result)
    assert "verdict" in d
    vd = d["verdict"]
    assert "overall" in vd
    assert "summary" in vd
    assert "findings" in vd
    assert isinstance(vd["findings"], list)
    assert len(vd["findings"]) == 5


def test_serialize_result_verdict_finding_shape() -> None:
    from backend.serialization import serialize_result
    result = _noise_result()
    d = serialize_result(result)
    for f in d["verdict"]["findings"]:
        assert "key" in f
        assert "title" in f
        assert "status" in f
        assert "headline" in f
        assert "detail" in f
        assert "stat" in f


def test_serialize_result_verdict_overall_is_string() -> None:
    from backend.serialization import serialize_result
    result = _noise_result()
    d = serialize_result(result)
    assert isinstance(d["verdict"]["overall"], str)
