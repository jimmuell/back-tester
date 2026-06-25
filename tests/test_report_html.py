from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from engine.config import APP_NAME
from engine.ingest.models import Trade
from engine.metrics.core import compute_metrics
from engine.report.html import render_report, write_report
from engine.timeutils import to_et


def _dt(s: str) -> datetime:
    return to_et(datetime.strptime(s, "%Y-%m-%d %H:%M"))


def _sample_metrics() -> object:
    trades = [
        Trade(1, "long", _dt("2024-01-02 09:30"), 5000.0,
              _dt("2024-01-02 10:00"), 5010.0, 1, 48.52),
        Trade(2, "short", _dt("2024-01-02 10:30"), 5010.0,
              _dt("2024-01-02 11:00"), 5020.0, 1, -52.48),
        Trade(3, "long", _dt("2024-01-02 11:30"), 5020.0,
              _dt("2024-01-02 12:00"), 5030.0, 1, 47.52),
    ]
    return compute_metrics(trades)


def test_render_contains_app_name() -> None:
    m = _sample_metrics()
    output = render_report(m)  # type: ignore[arg-type]
    assert APP_NAME in output


def test_render_custom_title() -> None:
    m = _sample_metrics()
    output = render_report(m, title="My Test Strategy")  # type: ignore[arg-type]
    assert "My Test Strategy" in output


def test_render_has_html_structure() -> None:
    m = _sample_metrics()
    output = render_report(m)  # type: ignore[arg-type]
    assert "<html" in output
    assert "</html>" in output
    assert "<table" in output


def test_render_has_svg() -> None:
    m = _sample_metrics()
    output = render_report(m)  # type: ignore[arg-type]
    assert "<svg" in output
    assert "<polyline" in output


def test_render_kpi_values_present() -> None:
    m = _sample_metrics()
    output = render_report(m)  # type: ignore[arg-type]
    # Total trades = 3
    assert ">3<" in output
    # Win rate = 2/3 ≈ 66.7%
    assert "66.7%" in output


def test_render_meta_included() -> None:
    m = _sample_metrics()
    meta = {"Profile": "edge", "Seed": "42"}
    output = render_report(m, meta=meta)  # type: ignore[arg-type]
    assert "edge" in output
    assert "42" in output


def test_write_report_creates_file() -> None:
    m = _sample_metrics()
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "report.html"
        write_report(m, out)  # type: ignore[arg-type]
        assert out.exists()
        content = out.read_text()
        assert APP_NAME in content


def test_xss_escaping() -> None:
    m = _sample_metrics()
    malicious = "<script>alert(1)</script>"
    output = render_report(m, title=malicious)  # type: ignore[arg-type]
    assert "<script>" not in output
    assert "&lt;script&gt;" in output
