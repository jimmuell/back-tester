"""FastAPI application — thin HTTP adapter over backtester.validate().

Synchronous validate() calls are made directly. When run times grow,
move them to asyncio.to_thread() or a job-queue pattern (ADR-002).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.serialization import serialize_result
from backtester import ValidationConfig, validate
from backtester.config import APP_NAME
from backtester.ingest.firstrate import BarDataError, load_bars
from backtester.ingest.tradingview import TradeListFormatError, load_trades

app = FastAPI(title=APP_NAME, version="0.2.0")

# Allow all origins for development; TASK 011 will restrict to the Next.js origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app_name": APP_NAME}


@app.post("/api/validate")
async def validate_endpoint(
    trades: Annotated[UploadFile, File(description="TradingView List of Trades CSV")],
    bars: Annotated[UploadFile | None, File(description="FirstRate ES bar data CSV")] = None,
    timeframe: Annotated[str, Form()] = "1day",
    adjustment: Annotated[str, Form()] = "ratio",
    seed: Annotated[int, Form()] = 42,
    mc_iterations: Annotated[int, Form()] = 10_000,
) -> dict[str, Any]:
    trade_bytes = await trades.read()
    bar_bytes = (await bars.read()) if bars is not None else None
    # Treat a 0-byte bars field (form submitted with no file selected) as absent.
    if not bar_bytes:
        bar_bytes = None

    trade_path: Path | None = None
    bar_path: Path | None = None
    try:
        # Write to temp files so existing Path-based loaders can read them.
        fd, tp = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        trade_path = Path(tp)
        trade_path.write_bytes(trade_bytes)

        if bar_bytes is not None:
            fd2, bp = tempfile.mkstemp(suffix=".csv")
            os.close(fd2)
            bar_path = Path(bp)
            bar_path.write_bytes(bar_bytes)

        # Load trades.
        try:
            trade_list = load_trades(trade_path)
        except (TradeListFormatError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Trade file error: {exc}") from exc

        # Load bars (optional).
        bar_set = None
        if bar_path is not None:
            try:
                bar_set = load_bars(
                    bar_path,
                    timeframe=timeframe,  # type: ignore[arg-type]
                    adjustment=adjustment,  # type: ignore[arg-type]
                )
            except (BarDataError, ValueError) as exc:
                raise HTTPException(status_code=422, detail=f"Bar file error: {exc}") from exc

        cfg = ValidationConfig(
            seed=seed,
            mc_iterations=mc_iterations,
            random_entry_iterations=mc_iterations,
        )

        try:
            result = validate(trade_list, bar_set, config=cfg)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return serialize_result(result)

    finally:
        if trade_path is not None:
            trade_path.unlink(missing_ok=True)
        if bar_path is not None:
            bar_path.unlink(missing_ok=True)
