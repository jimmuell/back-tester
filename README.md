# BackTester (working title)

A standalone app that validates trading strategies for a genuine, persistent statistical edge — not just a profitable backtest. Analyzes TradingView-exported trade lists for MES futures using Monte Carlo, in/out-of-sample testing, walk-forward analysis, regime analysis, multiple-testing controls (Deflated Sharpe, PBO), and a prop-firm challenge simulator.

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — statistical methodology
- [`docs/BUILD_SPEC.md`](docs/BUILD_SPEC.md) — architecture, modules, data contracts, phasing
- [`docs/DIVISION_OF_LABOR.md`](docs/DIVISION_OF_LABOR.md) — how the team works
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — decision log (ADR-style)

## Dev quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[dev]"
pytest -q                        # 2 passed
ruff check .
mypy engine
```
