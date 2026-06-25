# DESIGN.md — Methodology

The canonical methodology for BackTester (working name). Defines what statistical validity means here and the tests that establish it. Owned by the Lead Engineer. Pairs with `BUILD_SPEC.md` (how it's built) and `DECISIONS.md` (why).

## North star

Answer one question: does a strategy have a genuine, persistent statistical edge, or is it the product of overfitting, selection bias, or chance? Every feature serves that distinction. Reports always separate two verdicts that are easy to conflate:

- **Statistical edge** — is the edge real and likely to persist?
- **Prop-firm EV** — would it profitably clear a funded-account challenge?

A strategy can be positive on the second and fail the first. The app must say so plainly.

## Why a profitable backtest is weak evidence

Three independent failure modes, each with its own countermeasure:

- **Overfitting** — rules describe noise in the specific history tested.
- **Selection bias (data snooping)** — the strategy/parameters were chosen because they looked best among many tried; the winner of a large search is biased upward.
- **Path luck** — even a real edge yields wildly different equity curves by trade order.

## Data integrity (checked before any metric is trusted)

- **Look-ahead bias** — decisions may use only information available at that moment. In the Pine round-trip MVP this is largely TradingView's responsibility, but generated Pine must be non-repainting (see `BUILD_SPEC.md`): higher-timeframe context consumed only on confirmed, closed bars.
- **Futures continuity** — use the ratio-adjusted continuous ES series for context/regime/benchmark; record the adjustment method with every run.
- **ES vs MES** — price series treated as equivalent; ES used for bars/context, MES economics ($5/point, $1.25/tick) applied to any app-side P&L. TradingView exports carry their own P&L.
- **Sample size** — record the trade count on every run; small samples make all other numbers unreliable and must trigger a low-confidence flag.

## Monte Carlo (methods kept distinct)

- **Trade-order shuffle** (resample without replacement) — same trades, randomized sequence. Mean return unchanged; reveals the distribution of drawdowns, losing streaks, time-under-water, and risk of ruin.
- **Bootstrap** (resample with replacement) — new samples from the trade set; reveals sampling uncertainty in the edge itself → confidence intervals on expectancy, profit factor, Sharpe.
- **Timing-aware / block resampling** — preserves calendar time and autocorrelation. Required for any time-dependent question (prop-firm timeout, time-to-payout); plain shuffling discards calendar time and would answer these dishonestly.
- **Assumption stress tests** — separately vary slippage, commissions, win rate, fills. This is sensitivity analysis, not resampling.

## The multiple-testing problem (our core differentiator)

The thing amateur pipelines skip. If many configurations are tried, some look excellent by chance. The app must:

- Track and report the number of configurations tested (trial count) for every result.
- **Deflated Sharpe Ratio** — adjusts observed Sharpe for trial count and non-normal returns.
- **Probability of Backtest Overfitting (PBO)** — via combinatorially symmetric cross-validation.
- Flag extreme in-sample → out-of-sample swings as suspect rather than celebrated (e.g., a regime filter that drops OOS drawdown from ~$116k to ~$2k is a red flag for overfitting or a too-small OOS sample, not a win — this is exactly the case the app exists to catch).

## Out-of-sample, walk-forward, regimes, benchmarks

- **OOS** — a held-out window never used in development; looked at once.
- **Walk-forward** — rolling and anchored; report per-window stability.
- **Regime tagging** — regimes defined by an explicit rule (trend filter / volatility band on the ES series), never by eye; performance broken out per regime.
- **Benchmarks** — every result compared to buy-and-hold and a random-entry strategy of equal exposure. If random entries with the same exit logic perform similarly, the edge is in risk management or exposure, not the signal.

## Metrics (with honest error bars)

Net/gross P&L, win rate, avg win/loss, expectancy, profit factor, Sharpe (with confidence interval), Sortino, max drawdown, recovery factor, Ulcer Index, streaks, avg trade duration, risk of ruin. Sharpe is reported as an interval, never a bare point estimate (its error widens with return autocorrelation). Plain t-tests are avoided in favor of bootstrap CIs and Deflated Sharpe, because trade returns are not i.i.d. normal.

## Prop-Firm Challenge Simulator (headline Phase-2 feature)

An application layer over timing-aware Monte Carlo. Models a configurable rule set — profit target, trailing/max drawdown, daily loss limit, minimum trading days, consistency rules, time limit, challenge fee, payout split — and reports, per firm preset or custom config:

- pass probability, payout probability, timeout probability
- net expected value after fees, mean payout, time-to-pass distribution

Firm presets (e.g., TopStep, Apex) carry numbers that change; they are verified at build time and treated as data, not hardcoded constants.

## Reproducibility

Every run stores: the strategy spec, generated Pine (if any), the trade list, the data window + adjustment method, all config, and the RNG seed — so any result can be audited and re-run.
