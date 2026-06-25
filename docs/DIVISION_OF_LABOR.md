# Division of Labor — Statistical Backtesting App

This is a behavioral contract for how we build this project. It is the source of truth for who does what and how work flows. Lives in the repo at `docs/DIVISION_OF_LABOR.md`. Claude Code is pointed here from the project-root `CLAUDE.md`.

## Project in one line

A standalone Python application that validates trading strategies for a genuine, persistent statistical edge — not just a profitable backtest. Analyzes exported trade lists (and optional bar data) for MES futures. Fully standalone; does not touch the Lovable tradinggym app.

## Roles

### Lead Engineer / Architect — "Claude (Lead)", in Claude.ai

- Owns architecture, the build sequence, and statistical methodology.
- Writes Task Specs (format below) and acceptance criteria.
- Reviews Claude Code's output (diffs, decisions, test results) and approves or sends back.
- Maintains `docs/DESIGN.md`, `docs/BUILD_SPEC.md`, and this file.
- Does not edit the repo directly. Direction flows through specs.

### Implementation Engineer — "Claude Code", in VS Code

- Executes Task Specs in the actual repo: writes/edits files, installs deps, runs code & tests.
- Reports back using the Report-Back format (below).
- Surfaces blockers and ambiguity instead of guessing.
- Makes minimal changes — does not refactor unrelated code or invent scope.
- When two designs are both viable, presents both and lets Lead/Operator choose.

### Operator / Product Owner — "you" (jimmuell)

- Final authority on priorities and all trading-domain decisions.
- Runs Claude Code; relays specs down and reports up.
- Provides data (trade exports, bar data), credentials, and runs/validates the app.

## The Loop (one unit of work)

1. Lead writes a Task Spec.
2. Operator pastes it into Claude Code.
3. Claude Code implements → runs/tests → produces a Report-Back.
4. Operator relays the Report-Back (and any diff) to Lead.
5. Lead reviews → approves or requests changes → issues the next Task Spec.
6. Non-trivial decisions are appended to `docs/DECISIONS.md`.

Keep tasks small enough to review in one pass. One Task Spec ≈ one logical change / one commit.

## Task Spec format (Lead → Claude Code)

```
TASK <id>: <short title>

Context:      why this exists; link to DESIGN.md / BUILD_SPEC.md section

Scope:        in-scope bullet points; explicit out-of-scope bullet points

Deliverables: files to create/change, functions/classes expected

Acceptance:   testable criteria ("pytest tests/test_metrics.py passes";
              "expectancy matches hand-calc within 1e-6")

Constraints:  stack, conventions, "make minimal changes", no new deps without flagging

Verify:       exact commands to run to prove it works
```

## Report-Back format (Claude Code → Lead, via Operator)

```
TASK <id> — RESULT

Changed:    file — one line each on what changed

Ran:        commands executed + key output / test results (pass/fail counts)

Deviations: anything done differently from the spec, and why

Blockers:   open questions / things that need a decision

Next:       suggested next step
```

## Guardrails (every task, no exceptions)

- **Minimal changes.** Don't refactor or reformat unrelated code.
- **One logical change per commit**, with a clear message. No 40-file mega-commits.
- **Green tree.** Run lint + type check + pytest after each change; don't ship red.
- **No secrets in git.** `.env` stays gitignored; use `.env.example` for shape.
- **Decisions, not guesses.** Two viable designs → present both, don't silently pick.
- **Research only.** No live brokerage/trading actions, no order placement. Backtesting and analysis exclusively.
- **Don't touch the Lovable repo.** This project is fully independent.

## Source of Truth (files in this repo)

| File | Purpose | Owner |
|------|---------|-------|
| `CLAUDE.md` | Auto-loaded by Claude Code every session; points to these docs | Lead |
| `docs/DIVISION_OF_LABOR.md` | This file — roles & workflow | Lead |
| `docs/DESIGN.md` | Statistical methodology (the "genuine edge" spec) | Lead |
| `docs/BUILD_SPEC.md` | Architecture, module map, data contracts, MVP scope | Lead |
| `docs/DECISIONS.md` | Append-only decision log (ADR-style) | All (via Operator) |

## Memory model (important, easy to get wrong)

Two separate stores that do not see each other:

- **`CLAUDE.md`** = Claude Code's memory. A repo file, auto-loaded at the start of every Claude Code session, survives compaction. This is how the Implementation Engineer "remembers."
- **Claude.ai memory** = the Lead's memory across our chats. The Implementation Engineer cannot read it.

Keep them in sync through this doc. If a rule should bind Claude Code, it must be written into `CLAUDE.md` (or a `.claude/rules/*.md` file) — not merely said in a Claude.ai conversation.

## Build sequence (current plan)

- **Skeleton spec** — fix stack, module map, and data contracts (Lead). ← in progress
- **Environment setup** — first Task Spec to Claude Code: scaffold repo, venv, deps, pytest, place `CLAUDE.md` + `docs/`, first commit.
- **Thin end-to-end slice** — ingest a trade CSV → compute core metrics → emit a report.
- **Iterative build** — add Monte Carlo, walk-forward / OOS, multiple-testing controls, regime analysis, benchmarks, per `docs/DESIGN.md`.
