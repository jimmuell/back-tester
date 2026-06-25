from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import engine
from engine.config import APP_NAME
from engine.metrics.core import Metrics
from engine.montecarlo.bootstrap import BootstrapResult
from engine.montecarlo.shuffle import ShuffleResult
from engine.orchestrator import ValidationResult
from engine.validation.benchmarks import BuyHoldResult, RandomEntryResult
from engine.validation.regimes import RegimeBreakdown
from engine.validation.splits import SplitResult
from engine.validation.walkforward import WalkForwardResult

_SVG_WIDTH = 700
_SVG_HEIGHT = 220
_SVG_PAD_LEFT = 55
_SVG_PAD_RIGHT = 20
_SVG_PAD_TOP = 15
_SVG_PAD_BOTTOM = 35

_HIST_WIDTH = 700
_HIST_HEIGHT = 160
_HIST_PAD_LEFT = 55
_HIST_PAD_RIGHT = 20
_HIST_PAD_TOP = 10
_HIST_PAD_BOTTOM = 30


def _equity_svg(curve: list[float]) -> str:
    """Render equity curve as an inline SVG polyline."""
    if len(curve) < 2:
        return "<p>Not enough trades to draw equity curve.</p>"

    w = _SVG_WIDTH - _SVG_PAD_LEFT - _SVG_PAD_RIGHT
    h = _SVG_HEIGHT - _SVG_PAD_TOP - _SVG_PAD_BOTTOM

    mn = min(curve)
    mx = max(curve)
    span = mx - mn if mx != mn else 1.0

    n = len(curve)

    def px(i: int) -> float:
        return _SVG_PAD_LEFT + (i / (n - 1)) * w

    def py(v: float) -> float:
        return _SVG_PAD_TOP + h - ((v - mn) / span) * h

    points = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(curve))
    zero_y = py(0.0)
    zero_y_clamped = max(_SVG_PAD_TOP, min(_SVG_PAD_TOP + h, zero_y))

    x_start = f"{_SVG_PAD_LEFT}"
    x_end = f"{_SVG_PAD_LEFT + w:.0f}"
    y_top = f"${mx:,.0f}"
    y_bot = f"${mn:,.0f}"

    color = "#22c55e" if curve[-1] >= 0 else "#ef4444"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{_SVG_WIDTH}" height="{_SVG_HEIGHT}" \
role="img" aria-label="Equity curve">
  <rect width="{_SVG_WIDTH}" height="{_SVG_HEIGHT}" fill="#0f172a" rx="6"/>
  <!-- zero line -->
  <line x1="{_SVG_PAD_LEFT}" y1="{zero_y_clamped:.1f}" \
x2="{_SVG_PAD_LEFT + w:.0f}" y2="{zero_y_clamped:.1f}" \
stroke="#475569" stroke-width="1" stroke-dasharray="4,3"/>
  <!-- equity curve -->
  <polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.8"/>
  <!-- y axis labels -->
  <text x="{_SVG_PAD_LEFT - 4}" y="{_SVG_PAD_TOP + 5:.0f}" \
text-anchor="end" font-size="10" fill="#94a3b8">{html.escape(y_top)}</text>
  <text x="{_SVG_PAD_LEFT - 4}" y="{_SVG_PAD_TOP + h:.0f}" \
text-anchor="end" font-size="10" fill="#94a3b8">{html.escape(y_bot)}</text>
  <!-- x axis labels -->
  <text x="{x_start}" y="{_SVG_PAD_TOP + h + 18:.0f}" \
font-size="10" fill="#94a3b8">Trade 1</text>
  <text x="{x_end}" y="{_SVG_PAD_TOP + h + 18:.0f}" \
text-anchor="end" font-size="10" fill="#94a3b8">Trade {n}</text>
</svg>"""


def _drawdown_hist_svg(dist: list[float], threshold: float) -> str:
    """Render a max-drawdown distribution as an inline SVG bar histogram."""
    if not dist:
        return "<p>No distribution data.</p>"

    n_bins = 40
    mn = min(dist)
    mx = max(dist)
    span = mx - mn if mx != mn else 1.0
    bin_w_val = span / n_bins

    counts = [0] * n_bins
    for v in dist:
        idx = min(int((v - mn) / bin_w_val), n_bins - 1)
        counts[idx] += 1

    max_count = max(counts) if counts else 1
    w = _HIST_WIDTH - _HIST_PAD_LEFT - _HIST_PAD_RIGHT
    h = _HIST_HEIGHT - _HIST_PAD_TOP - _HIST_PAD_BOTTOM
    bar_w = w / n_bins

    bars = ""
    for i, count in enumerate(counts):
        bar_h = (count / max_count) * h
        x = _HIST_PAD_LEFT + i * bar_w
        y = _HIST_PAD_TOP + h - bar_h
        bar_val = mn + (i + 0.5) * bin_w_val
        color = "#ef4444" if bar_val >= threshold else "#38bdf8"
        bars += (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w - 1:.1f}" '
            f'height="{bar_h:.1f}" fill="{color}" opacity="0.8"/>\n'
        )

    # Threshold marker line
    thresh_x = _HIST_PAD_LEFT + ((threshold - mn) / span) * w
    thresh_x_clamped = max(_HIST_PAD_LEFT, min(_HIST_PAD_LEFT + w, thresh_x))
    thresh_line = (
        f'<line x1="{thresh_x_clamped:.1f}" y1="{_HIST_PAD_TOP}" '
        f'x2="{thresh_x_clamped:.1f}" y2="{_HIST_PAD_TOP + h:.0f}" '
        f'stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="4,3"/>'
    )

    # x-axis labels (min, threshold, max)
    x_mn = _HIST_PAD_LEFT
    x_mx = _HIST_PAD_LEFT + w
    label_y = _HIST_PAD_TOP + h + 18

    return f"""<svg xmlns="http://www.w3.org/2000/svg" \
width="{_HIST_WIDTH}" height="{_HIST_HEIGHT}" \
role="img" aria-label="Max drawdown distribution">
  <rect width="{_HIST_WIDTH}" height="{_HIST_HEIGHT}" fill="#0f172a" rx="6"/>
  {bars}
  {thresh_line}
  <text x="{x_mn}" y="{label_y:.0f}" font-size="10" fill="#94a3b8">\
${mn:,.0f}</text>
  <text x="{thresh_x_clamped:.1f}" y="{label_y:.0f}" text-anchor="middle" \
font-size="10" fill="#fbbf24">threshold</text>
  <text x="{x_mx}" y="{label_y:.0f}" text-anchor="end" font-size="10" fill="#94a3b8">\
${mx:,.0f}</text>
</svg>"""


def _fmt_usd(v: float) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.2f}"


def _fmt_pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _bootstrap_section(bs: BootstrapResult) -> str:
    ci_pct = f"{int(bs.ci_level * 100)}%"

    def _pf_fmt(v: float) -> str:
        return "∞" if v == float("inf") else f"{v:.2f}"

    def _ci_row(label: str, point: float, ci: tuple[float, float], fmt: str) -> str:
        lo, hi = ci
        if fmt == "usd":
            p_s = html.escape(_fmt_usd(point))
            lo_s = html.escape(_fmt_usd(lo))
            hi_s = html.escape(_fmt_usd(hi))
        elif fmt == "pct":
            p_s = html.escape(_fmt_pct(point))
            lo_s = html.escape(_fmt_pct(lo))
            hi_s = html.escape(_fmt_pct(hi))
        else:
            p_s = html.escape(_pf_fmt(point))
            lo_s = html.escape(f"{lo:.2f}")
            hi_s = html.escape(f"{hi:.2f}")
        pos_cls = "pos" if point >= 0 else "neg"
        return (
            f"<tr><td>{html.escape(label)}</td>"
            f'<td class="{pos_cls}">{p_s}</td>'
            f"<td>{lo_s} — {hi_s}</td></tr>\n"
        )

    rows = (
        _ci_row("Expectancy", bs.expectancy_point, bs.expectancy_ci, "usd")
        + _ci_row("Net Profit", bs.net_profit_point, bs.net_profit_ci, "usd")
        + _ci_row("Profit Factor", bs.profit_factor_point, bs.profit_factor_ci, "pf")
        + _ci_row("Win Rate", bs.win_rate_point, bs.win_rate_ci, "pct")
    )
    inf_note = (
        f'<p class="sub">{html.escape(str(bs.n_inf_pf))} of '
        f"{html.escape(str(bs.n_iterations))} resamples had no losses "
        f"(PF = ∞) — excluded from PF CI.</p>"
        if bs.n_inf_pf > 0
        else ""
    )

    return f"""<section>
  <h2>Bootstrap {html.escape(ci_pct)} Confidence Intervals
    <span class="sub"> ({html.escape(str(bs.n_iterations))} iterations)</span>
  </h2>
  <table class="kpi">
    <thead><tr>
      <th style="text-align:left;color:#94a3b8;padding:0.35rem 0.75rem">Metric</th>
      <th style="text-align:left;color:#94a3b8;padding:0.35rem 0.75rem">Point</th>
      <th style="text-align:left;color:#94a3b8;padding:0.35rem 0.75rem">\
{html.escape(ci_pct)} CI [lo — hi]</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {inf_note}
</section>"""


def _shuffle_section(sh: ShuffleResult) -> str:
    p = sh.max_drawdown_pctiles
    pctile_rows = "".join(
        f"<tr><td>{html.escape(f'P{k}')}</td>"
        f'<td class="neg">{html.escape(_fmt_usd(p[k]))}</td></tr>\n'
        for k in sorted(p)
    )
    ror_cls = "neg" if sh.risk_of_ruin > 0.5 else ("" if sh.risk_of_ruin > 0.2 else "pos")
    hist_svg = _drawdown_hist_svg(sh.max_drawdown_dist, sh.ruin_threshold)

    return f"""<section>
  <h2>Trade-Order Shuffle — Drawdown Distribution
    <span class="sub"> ({html.escape(str(sh.n_iterations))} iterations)</span>
  </h2>
  <p class="sub">Net P&amp;L is invariant (same trades, varied order).
    Blue bars = drawdown below threshold; red bars = above threshold (yellow line).
  </p>
  {hist_svg}
  <table class="kpi" style="margin-top:0.75rem">
    <tbody>
      {pctile_rows}
      <tr><td>Threshold (observed DD)</td>
          <td class="neg">{html.escape(_fmt_usd(sh.ruin_threshold))}</td></tr>
      <tr><td>Risk of exceeding threshold</td>
          <td class="{ror_cls}">{html.escape(_fmt_pct(sh.risk_of_ruin))}</td></tr>
    </tbody>
  </table>
</section>"""


def _split_section(sp: SplitResult) -> str:
    """IS vs OOS side-by-side comparison with edge_decayed flag."""

    def _kpi_col(label: str, is_val: str, oos_val: str) -> str:
        return (
            f"<tr><td>{html.escape(label)}</td>"
            f"<td>{html.escape(is_val)}</td>"
            f"<td>{html.escape(oos_val)}</td></tr>\n"
        )

    def _pf(v: float) -> str:
        return "∞" if v == float("inf") else f"{v:.2f}"

    is_m = sp.in_sample
    oos_m = sp.out_sample

    rows = (
        _kpi_col("Trades", str(is_m.total_trades), str(oos_m.total_trades))
        + _kpi_col("Win Rate", _fmt_pct(is_m.win_rate), _fmt_pct(oos_m.win_rate))
        + _kpi_col("Expectancy", _fmt_usd(is_m.expectancy), _fmt_usd(oos_m.expectancy))
        + _kpi_col("Net Profit", _fmt_usd(is_m.net_profit), _fmt_usd(oos_m.net_profit))
        + _kpi_col("Profit Factor", _pf(is_m.profit_factor), _pf(oos_m.profit_factor))
        + _kpi_col("Max Drawdown", _fmt_usd(is_m.max_drawdown), _fmt_usd(oos_m.max_drawdown))
    )

    decay_cls = "neg" if sp.edge_decayed else "pos"
    decay_label = "⚠ EDGE DECAYED (IS positive → OOS ≤ 0)" if sp.edge_decayed else "Edge consistent"
    ratio_str = (
        f"{sp.expectancy_ratio:.2f}×"
        if not (sp.expectancy_ratio != sp.expectancy_ratio)  # NaN guard
        else "N/A"
    )

    return f"""<section>
  <h2>Temporal Stability — In-Sample vs Out-of-Sample
    <span class="sub"> (OOS = {html.escape(_fmt_pct(sp.oos_fraction))} of trades
      | split at {html.escape(sp.split_time.strftime('%Y-%m-%d %H:%M'))} ET)</span>
  </h2>
  <p class="sub">Chronological hold-out consistency check — not optimize-IS/validate-OOS
    (see ADR-013).</p>
  <table class="kpi">
    <thead><tr>
      <th style="text-align:left;color:#94a3b8;padding:0.35rem 0.75rem">Metric</th>
      <th style="text-align:left;color:#94a3b8;padding:0.35rem 0.75rem">In-Sample</th>
      <th style="text-align:left;color:#94a3b8;padding:0.35rem 0.75rem">Out-of-Sample</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p><strong class="{decay_cls}">{html.escape(decay_label)}</strong>
     &nbsp;|&nbsp; Expectancy ratio (OOS/IS): {html.escape(ratio_str)}</p>
</section>"""


def _walkforward_section(wf: WalkForwardResult) -> str:
    """Walk-forward window table + stability summary."""
    header = (
        "<tr>"
        "<th>Window</th><th>Trades</th><th>Expectancy</th>"
        "<th>Net Profit</th><th>Win Rate</th><th>Profit Factor</th><th>Max DD</th>"
        "</tr>\n"
    )

    def _pf(v: float) -> str:
        return "∞" if v == float("inf") else f"{v:.2f}"

    rows = ""
    for w in wf.windows:
        exp_cls = "pos" if w.expectancy >= 0 else "neg"
        period = (
            f"{w.start_time.strftime('%m/%d/%y')}–{w.end_time.strftime('%m/%d/%y')}"
        )
        rows += (
            f"<tr>"
            f"<td>W{w.index + 1} <span class='sub'>{html.escape(period)}</span></td>"
            f"<td>{w.n_trades}</td>"
            f'<td class="{exp_cls}">{html.escape(_fmt_usd(w.expectancy))}</td>'
            f"<td>{html.escape(_fmt_usd(w.net_profit))}</td>"
            f"<td>{html.escape(_fmt_pct(w.win_rate))}</td>"
            f"<td>{html.escape(_pf(w.profit_factor))}</td>"
            f'<td class="neg">{html.escape(_fmt_usd(w.max_drawdown))}</td>'
            f"</tr>\n"
        )

    pct_pos_cls = "pos" if wf.pct_windows_positive >= 0.6 else "neg"

    return f"""<section>
  <h2>Walk-Forward Stability
    <span class="sub"> ({html.escape(str(wf.n_windows))} windows,
      {html.escape(wf.scheme)} scheme)</span>
  </h2>
  <p class="sub">Contiguous equal-count time segments — temporal consistency check,
    not walk-forward optimization (ADR-013).</p>
  <table class="kpi" style="min-width:600px">
    <thead style="color:#94a3b8;font-size:0.85rem">{header}</thead>
    <tbody>{rows}</tbody>
  </table>
  <p>
    <strong class="{pct_pos_cls}">{html.escape(_fmt_pct(wf.pct_windows_positive))}</strong>
    of windows positive &nbsp;|&nbsp;
    Expectancy mean {html.escape(_fmt_usd(wf.expectancy_mean))},
    std {html.escape(_fmt_usd(wf.expectancy_std))}
  </p>
</section>"""


_REGIME_ORDER: dict[str, int] = {
    # trend
    "bull": 0, "range": 1, "bear": 2,
    # volatility
    "high_vol": 0, "low_vol": 1,
    # fallback
    "undefined": 99,
}


def _regime_section(rb: RegimeBreakdown) -> str:
    def _pf(v: float) -> str:
        return "∞" if v == float("inf") else f"{v:.2f}"

    header = (
        "<tr>"
        "<th>Regime</th><th>Trades</th><th>Expectancy</th>"
        "<th>Win Rate</th><th>Net Profit</th><th>Profit Factor</th>"
        "</tr>\n"
    )

    sorted_regimes = sorted(
        rb.per_regime.items(),
        key=lambda kv: _REGIME_ORDER.get(kv[0], 50),
    )

    rows = ""
    for label, m in sorted_regimes:
        exp_cls = "pos" if m.expectancy >= 0 else "neg"
        rows += (
            f"<tr>"
            f"<td>{html.escape(label)}</td>"
            f"<td>{m.total_trades}</td>"
            f'<td class="{exp_cls}">{html.escape(_fmt_usd(m.expectancy))}</td>'
            f"<td>{html.escape(_fmt_pct(m.win_rate))}</td>"
            f"<td>{html.escape(_fmt_usd(m.net_profit))}</td>"
            f"<td>{html.escape(_pf(m.profit_factor))}</td>"
            f"</tr>\n"
        )

    params_str = ", ".join(f"{k}={v}" for k, v in rb.params.items()) if rb.params else ""
    sub = f" ({html.escape(params_str)})" if params_str else ""

    return f"""<section>
  <h2>Regime Breakdown — {html.escape(rb.scheme)}{sub}</h2>
  <p class="sub">Regime label assigned to each trade from the most recent bar at/before
    entry time (non-look-ahead, trailing windows only).</p>
  <table class="kpi" style="min-width:560px">
    <thead style="color:#94a3b8;font-size:0.85rem">{header}</thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""


def _random_entry_section(re: RandomEntryResult) -> str:
    beats_cls = "pos" if re.beats_random else "neg"
    beats_label = (
        f"✓ Beats random entry (P{int(re.threshold * 100)})"
        if re.beats_random
        else f"✗ Does not beat random entry (P{int(re.threshold * 100)})"
    )
    rank_pct = f"{re.net_percentile_rank * 100:.1f}th percentile"
    p = re.random_net_pctiles

    def _prow(label: str, val: float) -> str:
        cls = "pos" if val >= 0 else "neg"
        return (
            f"<tr><td>{html.escape(label)}</td>"
            f'<td class="{cls}">{html.escape(_fmt_usd(val))}</td></tr>\n'
        )

    strat_cls = "pos" if re.strategy_net >= 0 else "neg"

    return f"""<section>
  <h2>Random-Entry Benchmark — Signal vs Exposure
    <span class="sub"> ({html.escape(str(re.n_iterations))} iterations,
      {html.escape(str(re.n_trades))} trades,
      {html.escape(f"{re.long_fraction:.0%}")} long)</span>
  </h2>
  <p class="sub">Random entries with the same trade count, holding-period distribution,
    and long/short mix — does the signal add value beyond pure exposure?
    Works in bar-index space; only valid when bars match the strategy instrument/period.</p>
  <table class="kpi">
    <tbody>
      <tr><td>Strategy Net</td>
          <td class="{strat_cls}">{html.escape(_fmt_usd(re.strategy_net))}</td></tr>
      {_prow("Random P95", p[95])}
      {_prow("Random P75", p[75])}
      {_prow("Random P50 (median)", p[50])}
      {_prow("Random P25", p[25])}
      {_prow("Random P5", p[5])}
    </tbody>
  </table>
  <p>Percentile rank: <strong>{html.escape(rank_pct)}</strong></p>
  <p><strong class="{beats_cls}">{html.escape(beats_label)}</strong></p>
</section>"""


def _buyhold_section(bh: BuyHoldResult) -> str:
    beats_cls = "pos" if bh.beats_buy_hold else "neg"
    beats_label = "✓ Beats buy-and-hold" if bh.beats_buy_hold else "✗ Does not beat buy-and-hold"
    strat_cls = "pos" if bh.strategy_net >= 0 else "neg"
    bh_cls = "pos" if bh.buy_hold_net >= 0 else "neg"

    return f"""<section>
  <h2>Buy-and-Hold Baseline
    <span class="sub"> ({html.escape(bh.instrument_symbol)},
      {html.escape(bh.start_time.strftime('%Y-%m-%d'))} —
      {html.escape(bh.end_time.strftime('%Y-%m-%d'))})</span>
  </h2>
  <p class="sub">Did the strategy outperform simply holding the instrument?
    Not a like-for-like exposure comparison — see the random-entry benchmark for that.</p>
  <table class="kpi">
    <tbody>
      <tr><td>Strategy Net</td>
          <td class="{strat_cls}">{html.escape(_fmt_usd(bh.strategy_net))}</td></tr>
      <tr><td>Buy-and-Hold Net</td>
          <td class="{bh_cls}">{html.escape(_fmt_usd(bh.buy_hold_net))}</td></tr>
      <tr><td>Entry bar close</td>
          <td>{html.escape(f"{bh.start_price:,.2f}")}</td></tr>
      <tr><td>Exit bar close</td>
          <td>{html.escape(f"{bh.end_price:,.2f}")}</td></tr>
    </tbody>
  </table>
  <p><strong class="{beats_cls}">{html.escape(beats_label)}</strong></p>
</section>"""


def _skipped_section(skipped: list[str]) -> str:
    if not skipped:
        return ""
    items = "\n".join(f"  <li>{html.escape(s)}</li>" for s in skipped)
    return f"""<section>
  <h2>Skipped Analyses</h2>
  <ul class="sub">
{items}
  </ul>
</section>"""


def render_report(
    metrics: Metrics,
    *,
    title: str | None = None,
    meta: dict[str, str] | None = None,
    shuffle: ShuffleResult | None = None,
    bootstrap: BootstrapResult | None = None,
    split: SplitResult | None = None,
    walk: WalkForwardResult | None = None,
    buy_hold: BuyHoldResult | None = None,
    random_entry_result: RandomEntryResult | None = None,
    regime: RegimeBreakdown | None = None,
    regimes: dict[str, RegimeBreakdown] | None = None,
    skipped: list[str] | None = None,
) -> str:
    app_name = html.escape(title or APP_NAME)
    generated_at = html.escape(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    version = html.escape(engine.__version__)

    meta_rows = ""
    if meta:
        for k, v in meta.items():
            meta_rows += (
                f"<tr><td>{html.escape(k)}</td>"
                f"<td>{html.escape(str(v))}</td></tr>\n"
            )

    pf = (
        f"{metrics.profit_factor:.2f}"
        if metrics.profit_factor != float("inf")
        else "∞"
    )
    pr = (
        f"{metrics.payoff_ratio:.2f}"
        if metrics.payoff_ratio != float("inf")
        else "∞"
    )

    kpi_rows = f"""
<tr><td>Total Trades</td><td>{metrics.total_trades}</td></tr>
<tr><td>Wins / Losses</td><td>{metrics.wins} / {metrics.losses}</td></tr>
<tr><td>Win Rate</td><td>{_fmt_pct(metrics.win_rate)}</td></tr>
<tr><td>Net Profit</td><td class="{'pos' if metrics.net_profit >= 0 else 'neg'}">\
{_fmt_usd(metrics.net_profit)}</td></tr>
<tr><td>Gross Profit</td><td class="pos">{_fmt_usd(metrics.gross_profit)}</td></tr>
<tr><td>Gross Loss</td><td class="neg">{_fmt_usd(metrics.gross_loss)}</td></tr>
<tr><td>Avg Win</td><td class="pos">{_fmt_usd(metrics.avg_win)}</td></tr>
<tr><td>Avg Loss</td><td class="neg">{_fmt_usd(metrics.avg_loss)}</td></tr>
<tr><td>Expectancy</td><td class="{'pos' if metrics.expectancy >= 0 else 'neg'}">\
{_fmt_usd(metrics.expectancy)}</td></tr>
<tr><td>Profit Factor</td><td>{html.escape(pf)}</td></tr>
<tr><td>Payoff Ratio</td><td>{html.escape(pr)}</td></tr>
<tr><td>Max Drawdown</td><td class="neg">{_fmt_usd(metrics.max_drawdown)}</td></tr>
<tr><td>Longest Win Streak</td><td>{metrics.longest_win_streak}</td></tr>
<tr><td>Longest Loss Streak</td><td>{metrics.longest_loss_streak}</td></tr>
"""

    svg = _equity_svg(metrics.equity_curve)

    meta_section = ""
    if meta_rows:
        meta_section = f"""
<section>
  <h2>Run Info</h2>
  <table class="kpi"><tbody>{meta_rows}</tbody></table>
</section>"""

    bootstrap_section = _bootstrap_section(bootstrap) if bootstrap is not None else ""
    shuffle_section = _shuffle_section(shuffle) if shuffle is not None else ""
    split_section = _split_section(split) if split is not None else ""
    walk_section = _walkforward_section(walk) if walk is not None else ""
    buyhold_section = _buyhold_section(buy_hold) if buy_hold is not None else ""
    random_entry_section = (
        _random_entry_section(random_entry_result) if random_entry_result is not None else ""
    )

    # Merge old single-regime param and new multi-regime dict; new dict takes precedence.
    all_regimes: dict[str, RegimeBreakdown] = {}
    if regime is not None:
        all_regimes[regime.scheme] = regime
    if regimes is not None:
        all_regimes.update(regimes)
    regime_sections = "".join(_regime_section(rb) for rb in all_regimes.values())

    skipped_section = _skipped_section(skipped) if skipped else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{app_name} — Strategy Report</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0;
         margin: 0; padding: 1.5rem; }}
  h1   {{ font-size: 1.4rem; margin: 0 0 0.25rem; color: #f8fafc; }}
  h2   {{ font-size: 1rem; color: #94a3b8; margin: 1.5rem 0 0.5rem; }}
  .sub {{ font-size: 0.8rem; color: #64748b; }}
  section {{ margin-bottom: 1.5rem; }}
  table.kpi {{ border-collapse: collapse; min-width: 320px; }}
  table.kpi td, table.kpi th {{ padding: 0.35rem 0.75rem;
    border-bottom: 1px solid #1e293b; font-size: 0.9rem; font-weight: normal; }}
  table.kpi td:first-child {{ color: #94a3b8; }}
  .pos {{ color: #4ade80; }}
  .neg {{ color: #f87171; }}
  svg  {{ display: block; border-radius: 6px; margin-top: 0.5rem; }}
  footer {{ font-size: 0.75rem; color: #334155; margin-top: 2rem; }}
</style>
</head>
<body>
<header>
  <h1>{app_name} — Strategy Report</h1>
  <p class="sub">Generated {generated_at} &nbsp;|&nbsp; engine v{version}</p>
</header>
{meta_section}
<section>
  <h2>Core Metrics</h2>
  <table class="kpi"><tbody>{kpi_rows}</tbody></table>
</section>
<section>
  <h2>Equity Curve</h2>
  {svg}
</section>
{bootstrap_section}
{shuffle_section}
{split_section}
{walk_section}
{buyhold_section}
{random_entry_section}
{regime_sections}
{skipped_section}
<footer>Research &amp; backtesting only — not financial advice.</footer>
</body>
</html>"""


def write_report(metrics: Metrics, path: Path, **kw: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics, **kw), encoding="utf-8")  # type: ignore[arg-type]


def render_full_report(
    result: ValidationResult,
    *,
    title: str | None = None,
    meta: dict[str, str] | None = None,
) -> str:
    """Render a complete HTML report from a ValidationResult."""
    return render_report(
        result.metrics,
        title=title,
        meta=meta,
        shuffle=result.shuffle,
        bootstrap=result.bootstrap,
        split=result.split,
        walk=result.walk_forward,
        buy_hold=result.buy_hold,
        random_entry_result=result.random_entry,
        regimes=result.regimes or None,
        skipped=result.skipped or None,
    )


def write_full_report(
    result: ValidationResult,
    path: Path,
    *,
    title: str | None = None,
    meta: dict[str, str] | None = None,
) -> None:
    """Write a complete HTML report from a ValidationResult to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_full_report(result, title=title, meta=meta), encoding="utf-8")
