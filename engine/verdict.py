"""Honest verdict and interpretation layer over ValidationResult.

Interprets ValidationResult fields into labeled Findings and an overall Verdict.
Computes NO new statistics — only interprets existing result fields.
See DESIGN.md (north star: never overclaim) and DECISIONS.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from engine.orchestrator import ValidationResult

VerdictStatus = Literal["pass", "caution", "fail", "inconclusive", "info"]

_MULTI_TESTING_NOTE = (
    "This is a single-test result. It has not yet been corrected for multiple testing "
    "(Deflated Sharpe Ratio and Probability of Backtest Overfitting are pending). "
    "A CI excluding zero is necessary but not sufficient to conclude a genuine edge."
)

_EXTREME_RANK_NOTE = (
    "Only extreme ranks (≥ threshold or ≤ 1 – threshold) are treated as conclusive. "
    "Mid-range ranks are consistent with both a genuine signal and random variation — "
    "this result does not distinguish between the two."
)

_MULTI_TESTING_CAVEAT = (
    " Note: multiple-testing controls (Deflated Sharpe, Probability of Backtest Overfitting) "
    "have not yet been applied — treat all findings as preliminary."
)


@dataclass(frozen=True)
class Finding:
    # "edge_vs_luck"|"path_risk"|"persistence"|"signal_vs_exposure"|"vs_buy_hold"
    key: str
    title: str
    status: VerdictStatus
    headline: str       # one honest sentence
    detail: str         # caveat / explanation
    stat: float | None  # the key number behind the finding


@dataclass(frozen=True)
class Verdict:
    findings: list[Finding]
    overall: VerdictStatus
    summary: str


# ── Individual finding generators ─────────────────────────────────────────────

def _edge_vs_luck(result: ValidationResult) -> Finding:
    lo, hi = result.bootstrap.expectancy_ci
    ci_pct = f"{int(result.bootstrap.ci_level * 100)}%"

    if lo > 0:
        return Finding(
            key="edge_vs_luck",
            title="Edge vs Luck",
            status="pass",
            headline=(
                f"{ci_pct} CI for expectancy excludes zero "
                f"(${lo:,.0f} – ${hi:,.0f}/trade). Positive bootstrap signal."
            ),
            detail=_MULTI_TESTING_NOTE,
            stat=lo,
        )

    if hi < 0:
        return Finding(
            key="edge_vs_luck",
            title="Edge vs Luck",
            status="fail",
            headline=(
                f"{ci_pct} CI for expectancy is entirely negative "
                f"(${lo:,.0f} – ${hi:,.0f}/trade). No positive edge detected."
            ),
            detail=(
                "The resampled distribution of per-trade expectancy lies below zero. "
                "Even before multiple-testing adjustment, the bootstrap evidence is negative."
            ),
            stat=lo,
        )

    return Finding(
        key="edge_vs_luck",
        title="Edge vs Luck",
        status="inconclusive",
        headline=(
            f"{ci_pct} CI brackets zero "
            f"(${lo:,.0f} – ${hi:,.0f}/trade). Cannot distinguish edge from luck."
        ),
        detail=(
            "The confidence interval spans both positive and negative expectancy. "
            "More trades or a stronger edge is needed for a clear signal."
        ),
        stat=lo,
    )


def _path_risk(result: ValidationResult) -> Finding:
    ror = result.shuffle.risk_of_ruin
    threshold = result.shuffle.ruin_threshold
    status: VerdictStatus = "caution" if ror > 0.5 else "info"

    return Finding(
        key="path_risk",
        title="Path Risk (Drawdown Distribution)",
        status=status,
        headline=(
            f"{ror:.0%} of trade-order shuffles reached a drawdown ≥ ${threshold:,.0f} "
            f"(the observed maximum)."
        ),
        detail=(
            "This is the fraction of all possible trade orderings — same trades, varied sequence — "
            "that produced a drawdown at or above the observed level. It is NOT an account-ruin "
            "probability, which requires specifying an account size. A high value indicates that "
            "path luck played a significant role in avoiding a severe drawdown."
        ),
        stat=ror,
    )


def _persistence(result: ValidationResult) -> Finding:
    sp = result.split
    wf = result.walk_forward

    if sp is None and wf is None:
        return Finding(
            key="persistence",
            title="Temporal Persistence",
            status="inconclusive",
            headline="Too few trades to run IS/OOS split or walk-forward stability checks.",
            detail=(
                "Both temporal-stability checks were skipped due to insufficient trade count. "
                "More trades are required to assess whether the edge is consistent over time."
            ),
            stat=None,
        )

    if sp is not None and sp.edge_decayed:
        ratio = sp.expectancy_ratio
        ratio_str = f"{ratio:.2f}×" if math.isfinite(ratio) else "N/A"
        return Finding(
            key="persistence",
            title="Temporal Persistence",
            status="fail",
            headline=(
                f"Edge decayed: IS expectancy ${sp.in_sample.expectancy:,.0f}/trade → "
                f"OOS expectancy ${sp.out_sample.expectancy:,.0f}/trade (ratio {ratio_str})."
            ),
            detail=(
                "In-sample expectancy was positive but out-of-sample expectancy dropped to zero "
                "or below. This is a strong signal of overfitting, regime change, or data snooping."
                " "
                "The chronological hold-out shows the edge did not transfer to unseen data."
            ),
            stat=ratio if math.isfinite(ratio) else None,
        )

    # Compute stat: prefer IS/OOS ratio when finite, else walk-forward pct.
    _ratio = sp.expectancy_ratio if sp is not None else float("nan")
    stat: float | None
    if math.isfinite(_ratio):
        stat = _ratio
    elif wf is not None:
        stat = wf.pct_windows_positive
    else:
        stat = None

    if wf is not None:
        pct = wf.pct_windows_positive
        wf_status: VerdictStatus = "pass" if pct >= 0.8 else "caution"
        return Finding(
            key="persistence",
            title="Temporal Persistence",
            status=wf_status,
            headline=(
                f"{pct:.0%} of walk-forward windows were profitable. "
                + (
                    "Edge appears stable."
                    if wf_status == "pass"
                    else "Edge is inconsistent across time windows."
                )
            ),
            detail=(
                "Walk-forward stability checks whether the edge holds across consecutive "
                "time segments. Below 80% positive windows is a concern. This is a "
                "temporal-consistency check, not an optimization/validation split (see ADR-013)."
            ),
            stat=stat,
        )

    # Only split available, not decayed.
    return Finding(
        key="persistence",
        title="Temporal Persistence",
        status="caution",
        headline="IS/OOS split passed (edge not decayed) but walk-forward could not be assessed.",
        detail=(
            "IS expectancy transferred to the out-of-sample window — encouraging. "
            "However, a single chronological split is weak evidence of persistence without "
            "walk-forward stability across multiple windows."
        ),
        stat=stat,
    )


def _signal_vs_exposure(result: ValidationResult) -> Finding:
    re = result.random_entry
    if re is None:
        return Finding(
            key="signal_vs_exposure",
            title="Signal vs Exposure",
            status="inconclusive",
            headline="No bar data provided — random-entry benchmark was not run.",
            detail=(
                "Upload a bar data file to run the random-entry benchmark. "
                "It tests whether the signal adds value beyond pure directional exposure "
                "by comparing the strategy against random entries with the same trade count, "
                "holding distribution, and long/short mix."
            ),
            stat=None,
        )

    rank = re.net_percentile_rank
    thr = re.threshold

    if rank >= thr:
        return Finding(
            key="signal_vs_exposure",
            title="Signal vs Exposure",
            status="pass",
            headline=(
                f"Strategy net is at the {rank:.1%} percentile of "
                f"{re.n_iterations:,} random-entry simulations (threshold {thr:.0%}). "
                "Signal adds value beyond exposure."
            ),
            detail=(
                "The strategy outperformed most random entries with the same exposure profile. "
                "Only extreme ranks (≥ threshold or ≤ 1 – threshold) are conclusive — "
                "this rank clears that bar."
            ),
            stat=rank,
        )

    if rank <= 1.0 - thr:
        return Finding(
            key="signal_vs_exposure",
            title="Signal vs Exposure",
            status="fail",
            headline=(
                f"Strategy net is at only the {rank:.1%} percentile of "
                f"{re.n_iterations:,} random-entry simulations. "
                "Signal underperforms pure exposure."
            ),
            detail=(
                "The strategy underperformed the majority of random entries with the same "
                "exposure profile. The entry signal is actively harmful relative to "
                "undirected exposure with the same holding periods and long/short mix."
            ),
            stat=rank,
        )

    return Finding(
        key="signal_vs_exposure",
        title="Signal vs Exposure",
        status="inconclusive",
        headline=(
            f"Strategy net is at the {rank:.1%} percentile of random-entry simulations — "
            "mid-range, not conclusive."
        ),
        detail=_EXTREME_RANK_NOTE,
        stat=rank,
    )


def _vs_buy_hold(result: ValidationResult) -> Finding:
    bh = result.buy_hold
    if bh is None:
        return Finding(
            key="vs_buy_hold",
            title="vs Buy-and-Hold",
            status="info",
            headline="No bar data provided — buy-and-hold comparison was not run.",
            detail=(
                "Upload a bar data file to compare the strategy against a simple buy-and-hold "
                "baseline over the same date range."
            ),
            stat=None,
        )

    beat = bh.beats_buy_hold
    delta = bh.strategy_net - bh.buy_hold_net
    return Finding(
        key="vs_buy_hold",
        title="vs Buy-and-Hold",
        status="info",
        headline=(
            f"Strategy (${bh.strategy_net:,.0f}) "
            f"{'beat' if beat else 'trailed'} "
            f"buy-and-hold (${bh.buy_hold_net:,.0f}) "
            f"by ${abs(delta):,.0f}."
        ),
        detail=(
            "This is a directional baseline only — not adjusted for exposure, holding periods, "
            "or risk. It is not a like-for-like comparison. Use the random-entry benchmark for "
            "exposure-controlled comparison. Low interpretive weight on its own."
        ),
        stat=delta,
    )


# ── Overall roll-up ───────────────────────────────────────────────────────────

_CORE_KEYS = frozenset({"edge_vs_luck", "persistence", "signal_vs_exposure"})


def summarize(result: ValidationResult) -> Verdict:
    """Produce an honest, labeled Verdict from a ValidationResult.

    Rules encoded in DESIGN.md. No new statistics are computed — only
    interpretation of existing result fields.

    CRITICAL: even an all-pass summary explicitly states the result is promising
    but NOT a confirmed edge until multiple-testing controls are applied.
    Never emit a bare 'edge confirmed'.
    """
    findings: list[Finding] = [
        _edge_vs_luck(result),
        _path_risk(result),
        _persistence(result),
        _signal_vs_exposure(result),
        _vs_buy_hold(result),
    ]

    core_statuses = [f.status for f in findings if f.key in _CORE_KEYS]

    overall: VerdictStatus
    summary: str

    if "fail" in core_statuses:
        overall = "fail"
        summary = (
            "At least one critical check failed. The evidence does not support a reliable "
            "edge at this time. Review the failing findings before drawing any conclusions."
            + _MULTI_TESTING_CAVEAT
        )
    elif any(s in ("inconclusive", "caution") for s in core_statuses):
        overall = "caution"
        summary = (
            "Results are mixed or inconclusive. Some checks suggest a potential edge but "
            "others raise uncertainty or lack enough data to be conclusive. "
            "Do not treat this as a confirmed edge."
            + _MULTI_TESTING_CAVEAT
        )
    else:
        overall = "pass"
        summary = (
            "All core checks are promising — but this result has NOT been corrected for "
            "multiple testing and must not be treated as a confirmed edge. "
            "A positive result here is necessary but not sufficient: "
            "Deflated Sharpe and Probability of Backtest Overfitting analysis "
            "are required before drawing strong conclusions."
        )

    return Verdict(findings=findings, overall=overall, summary=summary)
