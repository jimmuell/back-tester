# BUILD_SPEC.md — Architecture & Build Plan

How BackTester (working name) is built. Owned by the Lead Engineer; implemented by Claude Code per `DIVISION_OF_LABOR.md`. Pairs with `DESIGN.md` (methodology).

## App identity

The display name is configurable from one source of truth. Default: `"BackTester"`.

- Single env var surfaced to both tiers: `APP_NAME` (backend) / `NEXT_PUBLIC_APP_NAME` (frontend), both defaulting to `"BackTester"`.
- No component, report, or page hardcodes the name; all read the config value.
- Repo/working folder: `backtester`. Renaming the product later = change the env var only.

## Three-tier architecture

```
Next.js (UI)  ──HTTP/JSON──▶  FastAPI (API)  ──direct──▶  backtester/ (pure-Python validation lib)
     │                              │
     │                              └──asyncpg/SQLAlchemy──▶  Postgres (local Supabase)
     └── Supabase Auth (deferred to SaaS phase)
```

- **Frontend** — Next.js (App Router), React, TypeScript, Tailwind, shadcn/ui, TanStack Query. Charts: lightweight-charts (canvas) for equity/price; uPlot (canvas) for many-series Monte Carlo fans; Recharts only for small KPI/summary visuals.
- **Backend** — FastAPI (async). Long runs use a job pattern: submit → job_id → progress via SSE/websocket → results. Connects directly to Postgres (not via Supabase REST) for full SQL and fast bulk inserts.
- **`backtester/`** — a pure-Python package (pandas/numpy/scipy/statsmodels) installable as `import backtester`, with no web or DB dependencies, unit-testable in isolation. This is where all of `DESIGN.md` lives.
- **Persistence** — local Supabase (Postgres + Studio + migrations in `supabase/migrations/`). Requires Docker Desktop running. Separate instance from the Lovable tradinggym project.

## Repo layout

```
backtester/
├── CLAUDE.md
├── docs/            DESIGN.md, BUILD_SPEC.md, DIVISION_OF_LABOR.md, DECISIONS.md
├── backtester/      pure-Python validation library (import backtester)
│   ├── ingest/      trade-list + bar-data loaders
│   ├── metrics/     KPIs, Sharpe CI, drawdown, etc.
│   ├── montecarlo/  shuffle, bootstrap, block
│   ├── validation/  IS/OOS, walk-forward, regimes, benchmarks, multiple-testing
│   ├── propsim/     prop-firm challenge engine (Phase 2)
│   ├── strategy/    canonical Strategy Spec model + Pine generator (Phase 2)
│   └── report/      HTML report builder
├── backend/         FastAPI app (imports backtester)
├── frontend/        Next.js app
├── supabase/        config.toml + migrations/
├── data/            gitignored; small committed sample under data/sample/
├── .env.example
└── pyproject.toml / package.json
```

## Data contracts

### Bar data — FirstRate ES (loader: `backtester/ingest/firstrate.py`)

- CSV, US Eastern (EST/EDT), no header by default.
- Columns: `timestamp, open, high, low, close, volume`; 1day files add a trailing `open_interest` column. Zero-volume bars are absent.
- Use the ratio-adjusted continuous series for context/regime/benchmark; loader records the adjustment method. Loader localizes to US/Eastern, normalizes to a tz-aware UTC index, and validates monotonic timestamps + gaps.
- Timeframes available: 1min, 5min, 30min, 1hour, 1day (history to ~2007).
- License: raw FirstRate data must not be redistributed → in SaaS, users supply their own; ship only a tiny illustrative sample in `data/sample/`.

### Trade list — TradingView "List of Trades" export (loader: `backtester/ingest/tradingview.py`)

- Accept CSV/XLSX. Pair entry/exit rows into one trade record. Be tolerant of column-name and version drift; validate and surface a clear error on unrecognized shape.
- Canonical internal trade record: `trade_id, direction(long/short), entry_time, entry_price, exit_time, exit_price, qty, pnl_gross, pnl_net, fees, bars_held, mae, mfe, tags{}`.

### Strategy Spec — canonical internal model (`backtester/strategy/spec.py`, Phase 2)

One schema, two producers (manual UI form and transcript extraction): `meta{name, instrument, timeframes{context, execution, trigger}, sessions, max_trades_per_day}`, `bias[]` (HTF PD-array rules → bias state), `setup{leg/fib, discount/premium thresholds, tolerance}`, `entry_trigger{LTF PD-array, wait_n_bars}`, `exit{stop+buffer, target rule, min_R}`, `risk{qty, commission, slippage}`, `supported_primitives[], unsupported_flags[], assumptions[]`.

## Execution model — Pine round-trip (MVP)

The app does not run strategies against bars in the MVP. Flow:

1. **Strategy in** — user defines a strategy (form) or pastes a YouTube/strategy transcript → AI extraction fills the Strategy Spec, listing every assumption and flagging anything outside the supported vocabulary (no inventing undetectable logic).
2. **User review** — user edits the interpreted spec + assumptions before anything runs. Reports state they validate our interpretation, not gospel.
3. **Pine generation** — spec → non-repainting Pine v6 `strategy()` script. Multi-timeframe via `request.security(..., lookahead=barmerge.lookahead_off)` on confirmed bars; tunables exposed as inputs (max trades/day, buffers, min R).
4. **User runs it** in TradingView and exports the List of Trades.
5. **Validate** — upload the trade list → full `DESIGN.md` pipeline → report.

Trade-off accepted: inherits TradingView's fill assumptions and is a multi-step round-trip. The full in-app engine (own data execution + concept-detector library + secure sandbox) is a later phase, deliberately deferred for speed.

## MVP scope & phasing

Execution order updated (ADR-012): the statistical engine (Monte Carlo + validation) is built before the FastAPI/Next.js UI. Slice numbers below are indicative, not strict.

- **Slice 0** (thin, no UI/DB): backtester ingests TradingView trade list → core metrics → HTML report. Driven by a script + pytest. Proves the pipe end-to-end.
- **Slice 1**: wrap in FastAPI + minimal Next.js UI (upload trade list, view report).
- **Slice 2**: Monte Carlo (shuffle + bootstrap), IS/OOS, walk-forward, benchmarks, regime tagging on ES bars.
- **Slice 3**: local Supabase persistence — runs, strategies, results history.
- **Slice 4**: Strategy input (manual form + transcript extraction) → Pine generation → round-trip.
- **Slice 5**: multiple-testing controls (Deflated Sharpe, PBO, trial tracking) + Prop-Firm Challenge Simulator with firm presets; dual verdict in reports.
- **Later phases**: in-app execution engine, concept-detector library, secure sandbox, SaaS auth (Supabase Auth + RLS) and billing (Stripe), deployment (Next.js→Vercel, FastAPI→Railway/Render/Fly).

## Stack

Python 3.12+, pandas, numpy, scipy, statsmodels; pytest; ruff + mypy. Node 20+, Next.js, React, TypeScript, Tailwind, shadcn/ui, TanStack Query, lightweight-charts, uPlot, Recharts. Research/backtesting only — no live trading or order placement.
