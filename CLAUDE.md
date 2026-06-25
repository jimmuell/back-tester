# Project: BackTester (working name — configurable, see Rules)

## What this is

A standalone app that validates trading strategies for a genuine, persistent statistical edge — not just a profitable backtest. Users either define a strategy or paste a strategy/YouTube transcript; the app extracts a canonical Strategy Spec, generates non-repainting Pine to run in TradingView, then validates the exported trade list with Monte Carlo, in/out-of-sample, walk-forward, regime analysis, multiple-testing controls (Deflated Sharpe, PBO), benchmarks, and a prop-firm challenge simulator. Reports give a dual verdict: statistical edge vs prop-firm EV.

Instrument focus: MES futures (ES price data + MES economics). This project is fully standalone — it does NOT touch the separate Lovable "tradinggym" app.

## Your role (Claude Code = Implementation Engineer)

A Lead Engineer (in Claude.ai) writes specs and reviews your output via the Operator. You implement in this repo: write/edit files, install deps, run code & tests, report back. Full workflow, Task Spec format, and Report-Back format are in `docs/DIVISION_OF_LABOR.md`.

## Architecture

Next.js (UI) ↔ FastAPI (API) ↔ `engine/` (pure-Python validation lib) ↔ Postgres (local Supabase). Backend connects directly to Postgres. Supabase Auth/RLS deferred to the SaaS phase. Long runs use a job pattern (submit → job_id → progress stream → results). See `docs/BUILD_SPEC.md`.

## Rules (bind every session)

- **App name is configurable.** Read `APP_NAME` / `NEXT_PUBLIC_APP_NAME` (default `"BackTester"`) everywhere — never hardcode the product name.
- Make minimal changes; don't refactor unrelated code. One logical change per commit.
- Run ruff + mypy + pytest after each change; don't leave the tree red.
- Never commit secrets; `.env` gitignored, maintain `.env.example`. Never commit raw FirstRate data (non-redistributable) — only the tiny sample in `data/sample/`.
- Generated Pine must be non-repainting (confirmed bars; `request.security` with `lookahead=barmerge.lookahead_off`).
- Transcript extraction must list assumptions and flag unsupported primitives; user reviews the spec before any run. Reports validate our interpretation, not gospel.
- Research/backtesting only — no live trading, order placement, or brokerage actions.
- Append non-trivial decisions to `docs/DECISIONS.md`.

## Stack

Python 3.12+, pandas, numpy, scipy, statsmodels, pytest, ruff, mypy. Node 20+, Next.js (App Router), React, TypeScript, Tailwind, shadcn/ui, TanStack Query, lightweight-charts, uPlot, Recharts.

## Build order (current)

Slice 0 thin pipe (trade list → metrics → report, no UI/DB) → **Monte Carlo + core statistical validation (engine-first, per ADR-012)** → FastAPI + minimal UI → OOS/walk-forward/regimes/benchmarks → Supabase persistence → strategy input + Pine generation → multiple-testing controls + prop-firm simulator. Details in `docs/BUILD_SPEC.md`.

## Key docs

- `docs/DIVISION_OF_LABOR.md` — how we work
- `docs/DESIGN.md` — methodology (genuine edge, dual verdict)
- `docs/BUILD_SPEC.md` — architecture, modules, data contracts, phasing
- `docs/DECISIONS.md` — decision log
