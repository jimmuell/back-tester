from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import engine
from engine.config import APP_NAME
from engine.metrics.core import Metrics
from engine.montecarlo.bootstrap import BootstrapResult
from engine.montecarlo.shuffle import ShuffleResult

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


def render_report(
    metrics: Metrics,
    *,
    title: str | None = None,
    meta: dict[str, str] | None = None,
    shuffle: ShuffleResult | None = None,
    bootstrap: BootstrapResult | None = None,
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
<footer>Research &amp; backtesting only — not financial advice.</footer>
</body>
</html>"""


def write_report(metrics: Metrics, path: Path, **kw: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics, **kw), encoding="utf-8")  # type: ignore[arg-type]
