"""FastAPI backend tests (TASK 010).

Uses starlette.testclient.TestClient (backed by httpx) to exercise /api/health
and POST /api/validate with various inputs.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backtester.ingest.synthetic import generate_bars, generate_trades, write_tradingview_csv

client = TestClient(app)

# ── Test-data helpers ─────────────────────────────────────────────────────────


def _tv_csv(n_trades: int = 30) -> bytes:
    """TradingView CSV bytes generated from synthetic trades."""
    trades = generate_trades(n_trades=n_trades, seed=42)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        p = Path(tf.name)
    write_tradingview_csv(trades, p)
    data = p.read_bytes()
    p.unlink()
    return data


def _fr_csv(n_bars: int = 252) -> bytes:
    """FirstRate daily CSV bytes (no header, 7 columns incl. open_interest)."""
    bars = generate_bars(n_bars=n_bars, seed=42)
    lines: list[str] = []
    for ts, row in bars.df.iterrows():
        date_str = ts.strftime("%Y-%m-%d")
        lines.append(
            f"{date_str},"
            f"{row['open']:.4f},"
            f"{row['high']:.4f},"
            f"{row['low']:.4f},"
            f"{row['close']:.4f},"
            f"{int(row['volume'])},"
            "0"
        )
    return "\n".join(lines).encode()


# ── /api/health ───────────────────────────────────────────────────────────────


def test_health_returns_200() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_health_response_shape() -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert "app_name" in body
    assert isinstance(body["app_name"], str)


# ── POST /api/validate — trades only ─────────────────────────────────────────


def test_validate_trades_only_returns_200() -> None:
    resp = client.post(
        "/api/validate",
        files={"trades": ("trades.csv", _tv_csv(), "text/csv")},
        data={"seed": "42", "mc_iterations": "500"},
    )
    assert resp.status_code == 200, resp.text


def test_validate_trades_only_has_required_keys() -> None:
    body = client.post(
        "/api/validate",
        files={"trades": ("trades.csv", _tv_csv(), "text/csv")},
        data={"seed": "42", "mc_iterations": "500"},
    ).json()
    for key in ("metrics", "shuffle", "bootstrap", "split", "walk_forward",
                "regimes", "skipped"):
        assert key in body, f"missing key: {key}"


def test_validate_metrics_fields() -> None:
    body = client.post(
        "/api/validate",
        files={"trades": ("trades.csv", _tv_csv(30), "text/csv")},
        data={"seed": "42", "mc_iterations": "500"},
    ).json()
    m = body["metrics"]
    assert m["total_trades"] == 30
    assert 0.0 <= m["win_rate"] <= 1.0
    assert isinstance(m["equity_curve"], list)
    assert len(m["equity_curve"]) == 30


def test_validate_trades_only_no_bars_analyses() -> None:
    """Without bars, buy_hold/random_entry are None and regimes is empty."""
    body = client.post(
        "/api/validate",
        files={"trades": ("trades.csv", _tv_csv(), "text/csv")},
        data={"seed": "42", "mc_iterations": "500"},
    ).json()
    assert body["buy_hold"] is None
    assert body["random_entry"] is None
    assert body["regimes"] == {}
    assert any("bars not provided" in s for s in body["skipped"])


def test_validate_split_present() -> None:
    body = client.post(
        "/api/validate",
        files={"trades": ("trades.csv", _tv_csv(30), "text/csv")},
        data={"seed": "42", "mc_iterations": "500"},
    ).json()
    assert body["split"] is not None
    assert "edge_decayed" in body["split"]
    assert "is_expectancy" in body["split"]
    assert "oos_expectancy" in body["split"]


def test_validate_bootstrap_ci_fields() -> None:
    body = client.post(
        "/api/validate",
        files={"trades": ("trades.csv", _tv_csv(30), "text/csv")},
        data={"seed": "42", "mc_iterations": "500"},
    ).json()
    bs = body["bootstrap"]
    assert "expectancy_point" in bs
    assert "expectancy_ci" in bs
    assert len(bs["expectancy_ci"]) == 2
    assert "profit_factor_ci" in bs


def test_validate_shuffle_fields() -> None:
    body = client.post(
        "/api/validate",
        files={"trades": ("trades.csv", _tv_csv(30), "text/csv")},
        data={"seed": "42", "mc_iterations": "500"},
    ).json()
    sh = body["shuffle"]
    assert "risk_of_ruin" in sh
    assert "max_drawdown_pctiles" in sh
    assert 0.0 <= sh["risk_of_ruin"] <= 1.0


# ── POST /api/validate — with bars ───────────────────────────────────────────


def test_validate_with_bars_returns_200() -> None:
    resp = client.post(
        "/api/validate",
        files={
            "trades": ("trades.csv", _tv_csv(), "text/csv"),
            "bars": ("bars.csv", _fr_csv(), "text/csv"),
        },
        data={"seed": "42", "mc_iterations": "500", "timeframe": "1day"},
    )
    assert resp.status_code == 200, resp.text


def test_validate_with_bars_has_regimes() -> None:
    body = client.post(
        "/api/validate",
        files={
            "trades": ("trades.csv", _tv_csv(), "text/csv"),
            "bars": ("bars.csv", _fr_csv(), "text/csv"),
        },
        data={"seed": "42", "mc_iterations": "500", "timeframe": "1day"},
    ).json()
    assert isinstance(body["regimes"], dict)
    # Regime schemes should both be present (bars cover the date range)
    for scheme in ("trend", "volatility"):
        if scheme in body["regimes"]:
            rb = body["regimes"][scheme]
            assert "trade_counts" in rb
            assert "per_regime" in rb


def test_validate_walkforward_in_response() -> None:
    body = client.post(
        "/api/validate",
        files={"trades": ("trades.csv", _tv_csv(30), "text/csv")},
        data={"seed": "42", "mc_iterations": "500"},
    ).json()
    if body["walk_forward"] is not None:
        wf = body["walk_forward"]
        assert "n_windows" in wf
        assert "pct_windows_positive" in wf
        assert isinstance(wf["windows"], list)


# ── POST /api/validate — error cases ─────────────────────────────────────────


def test_validate_garbage_csv_returns_422() -> None:
    resp = client.post(
        "/api/validate",
        files={"trades": ("trades.csv", b"not,a,valid,tradingview,file\n1,2,3,4,5", "text/csv")},
        data={"seed": "42", "mc_iterations": "500"},
    )
    assert resp.status_code == 422


def test_validate_empty_csv_returns_422() -> None:
    resp = client.post(
        "/api/validate",
        files={"trades": ("trades.csv", b"", "text/csv")},
        data={"seed": "42", "mc_iterations": "500"},
    )
    assert resp.status_code == 422


def test_validate_bad_bars_returns_422() -> None:
    resp = client.post(
        "/api/validate",
        files={
            "trades": ("trades.csv", _tv_csv(), "text/csv"),
            "bars": ("bars.csv", b"garbage bar data", "text/csv"),
        },
        data={"seed": "42", "mc_iterations": "500", "timeframe": "1day"},
    )
    assert resp.status_code == 422


def test_validate_missing_trades_field_returns_422() -> None:
    """FastAPI validates required form fields; missing trades → 422."""
    resp = client.post("/api/validate", data={"seed": "42"})
    assert resp.status_code == 422


# ── Determinism ───────────────────────────────────────────────────────────────


def test_validate_deterministic() -> None:
    tv = _tv_csv(30)
    kwargs: dict = dict(
        files={"trades": ("trades.csv", tv, "text/csv")},
        data={"seed": "7", "mc_iterations": "500"},
    )
    r1 = client.post("/api/validate", **kwargs).json()
    r2 = client.post("/api/validate", **kwargs).json()
    assert r1["metrics"]["net_profit"] == r2["metrics"]["net_profit"]
    assert r1["shuffle"]["risk_of_ruin"] == r2["shuffle"]["risk_of_ruin"]
    assert r1["bootstrap"]["expectancy_point"] == r2["bootstrap"]["expectancy_point"]


# ── /api/health app_name env var ─────────────────────────────────────────────


def test_health_app_name_is_string() -> None:
    body = client.get("/api/health").json()
    assert isinstance(body["app_name"], str)
    assert len(body["app_name"]) > 0
