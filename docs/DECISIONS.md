# DECISIONS.md — Decision Log

Append-only. Newest at the bottom. One entry per non-trivial choice: decision, why, alternatives, consequences. Keep entries short.

---

**ADR-001 — Standalone app, separate from the Lovable "tradinggym" repo**
Decision: Build a new, fully independent project ("Option A"). Do not modify or depend on the Lovable app's code. Why: The Lovable app is a production-ish multi-feature platform (auth, payments, LMS); heavy, iterative quant compute doesn't belong inside it and Lovable's regeneration fights hand-engineering. Alternatives: Upgrade the existing app's backtest module (rejected: risk + tool friction); shared-DB variant (deferred). Consequences: Clean slate; we re-implement, not fork. The real engine wasn't in that repo anyway (it lived in an external service).

---

**ADR-002 — Three-tier stack: Next.js + FastAPI + pure-Python engine**
Decision: Next.js (App Router) UI ↔ FastAPI ↔ a dependency-free Python validation library. Why: Compute must stay in Python (pandas/numpy/scipy). "Next.js vs React" is a non-question — Next is React plus the SaaS surface (SSR/SEO, auth, API) the stated destination needs. Alternatives: Vite SPA (lighter, but bolts on SaaS pieces later); JS-only (rejects the math ecosystem). Consequences: Two-language repo; async job pattern for long runs; chart libs matched to data size (lightweight-charts/uPlot for heavy series, Recharts for summaries).

---

**ADR-003 — Persistence: local Supabase (Postgres), backend connects directly to Postgres**
Decision: Start on a local Supabase instance. FastAPI talks directly to Postgres (SQLAlchemy/asyncpg); Supabase Auth/RLS reserved for the SaaS phase. Why: Known from the Lovable build; clean path to hosted SaaS (same migrations); Postgres fits trade lists + JSONB results. Direct connection avoids REST overhead for bulk/heavy I/O. Alternatives: Plain Postgres/SQLite (lighter, but migration cost later); routing analytics through Supabase REST (rejected: overhead). Consequences: Requires Docker Desktop. The thin slice runs DB-free; Supabase enters at Slice 3.

---

**ADR-004 — Execution model: Pine round-trip for the MVP**
Decision: MVP turns a strategy into non-repainting Pine; the user runs it in TradingView and exports the trade list, which the app validates. No in-app bar execution in the MVP. Why: Far smaller, faster build — no historical execution engine, concept-detector library, or secure sandbox required to ship value. Alternatives: Full in-app engine first (rejected for MVP: large build); chosen as a later phase to architect toward. Consequences: Inherits TradingView fill assumptions; multi-step round-trip. Pine generator must guarantee non-repainting multi-timeframe logic.

---

**ADR-005 — Dual input: transcript paste and manual strategy definition**
Decision: Both inputs converge on one canonical Strategy Spec; everything downstream is input-agnostic. Transcript extraction must list assumptions and flag unsupported primitives, with a mandatory user-review step before running. Why: Matches the product vision (evaluate influencer strategies and user-defined ones) and keeps it one app, not two. Extraction is lossy, so review is a safety rail and a differentiator. Consequences: Need a constrained-but-extensible primitive vocabulary; reports state they validate our interpretation.

---

**ADR-006 — Bar data: FirstRate ES, ratio-adjusted continuous series**
Decision: Standardize on FirstRate's ratio-adjusted continuous ES series for context/regime/benchmark. Use ES bars with MES economics ($5/pt, $1.25/tick) for app-side P&L. Why: ES has long, clean history (~2007) and equals MES in price; user trades MES. Ratio-adjusted continuous is the vendor's backtesting-recommended series. Consequences: Loader handles US/Eastern tz, header-less CSV, 1day open-interest column. Raw FirstRate data is non-redistributable → SaaS users bring their own data; ship only a tiny sample.

---

**ADR-007 — Configurable global app name (default "BackTester")**
Decision: Product name comes from one config value (`APP_NAME` / `NEXT_PUBLIC_APP_NAME`, default `"BackTester"`); nothing hardcodes it. Why: Final name undecided; renaming must be a one-line change. Consequences: All UI/reports/pages read the config value. Repo folder: `backtester`.

---

**ADR-008 — Prop-Firm Challenge Simulator as headline Phase-2 feature**
Decision: Build a configurable funded-account simulator over timing-aware Monte Carlo (pass/payout/timeout probability, net EV after fees). Core validation engine first; simulator in Phase 2. Why: Target users trade prop evaluations; this is a concrete SaaS wedge generic backtesters lack. It sits cleanly atop the Monte Carlo engine, so the engine must be right first. Consequences: Needs timing-aware/block resampling (plain shuffle can't answer timeout). Firm presets are data, verified at build time.

---

**ADR-009 — Python tooling: .venv + pip + pyproject (PEP 621, setuptools)**
Decision: standard `python -m venv .venv` + pip, project metadata/deps/tool config in `pyproject.toml`. Why: universal, zero-friction, no extra tooling to install. Alternatives: uv (faster — may adopt later as a drop-in), Poetry (heavier). Consequences: dev installs via `pip install -e ".[dev]"`.

---

### ADR-010 — Timezones: stdlib zoneinfo + tzdata (drop pytz)
**Decision:** Use stdlib `zoneinfo` for all tz handling; add `tzdata` for Windows; canonical zone "America/New_York". Remove pytz/types-pytz.
**Why:** pytz's non-standard `localize()` API is a known datetime footgun; zoneinfo (PEP 615) is the modern stdlib approach and drops a dependency.
**Consequences:** Shared `engine/timeutils.py` (ET constant + `to_et` helper). zoneinfo still accepts "US/Eastern" as an alias, so persisted strings stay valid.

---

### ADR-011 — Python floor standardized at 3.12
**Decision:** `requires-python = ">=3.12"`, matching `mypy python_version` and `ruff target-version = "py312"`.
**Why:** TASK 002 surfaced a mismatch (runtime >=3.11 vs mypy 3.12); 3.12-only code could pass type checks yet fail at runtime. No product reason to support 3.11; current numpy stubs assume 3.12.
**Alternatives:** Keep 3.11 and upgrade mypy to parse PEP 695 stubs (rejected: more friction for no benefit).
**Consequences:** Consistency across runtime, type-checker, and linter.

---

### ADR-012 — Build the statistical engine before the UI
**Decision:** Do Monte Carlo + core statistical validation before the FastAPI/Next.js UI.
**Why:** The engine is the core value/differentiator, pure-Python (fast, no infra), and a UI built now would be reworked once richer outputs exist; the HTML report already gives visibility.
**Alternatives:** UI-first to de-risk full-stack integration sooner (deferred; integration risk is low).
**Consequences:** UI is built once over richer engine output; slice numbering is indicative.
