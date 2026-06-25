import type { BuyHold, RandomEntry } from "@/lib/types";
import { currency, pct, num, shortDate } from "@/lib/format";

interface Props {
  buyHold: BuyHold | null;
  randomEntry: RandomEntry | null;
}

export default function BenchmarksSection({ buyHold, randomEntry }: Props) {
  if (!buyHold && !randomEntry) return null;

  return (
    <div className="space-y-4">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        Benchmarks
      </h2>

      {buyHold && (
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-300">
              vs Buy-and-hold ({buyHold.instrument_symbol})
            </h3>
            <span
              className={`text-xs rounded-full px-2 py-0.5 ring-1 ${
                buyHold.beats_buy_hold
                  ? "bg-emerald-600/20 text-emerald-300 ring-emerald-500/40"
                  : "bg-slate-600/20 text-slate-300 ring-slate-500/40"
              }`}
            >
              {buyHold.beats_buy_hold ? "Beat" : "Trailed"}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt className="text-slate-500">Strategy net</dt>
              <dd className="font-mono text-slate-200 mt-0.5">{currency(buyHold.strategy_net)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Buy-and-hold net</dt>
              <dd className="font-mono text-slate-200 mt-0.5">{currency(buyHold.buy_hold_net)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Period</dt>
              <dd className="text-slate-300 mt-0.5">
                {shortDate(buyHold.start_time)} – {shortDate(buyHold.end_time)}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Price range</dt>
              <dd className="font-mono text-slate-300 mt-0.5">
                {num(buyHold.start_price, 2)} → {num(buyHold.end_price, 2)}
              </dd>
            </div>
          </div>
          <p className="text-xs text-slate-500">
            Directional baseline only — not adjusted for exposure, holding periods, or risk.
            Low interpretive weight on its own.
          </p>
        </div>
      )}

      {randomEntry && (
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-300">
              Random-entry benchmark ({randomEntry.n_iterations.toLocaleString()} sims)
            </h3>
            <span
              className={`text-xs rounded-full px-2 py-0.5 ring-1 ${
                randomEntry.beats_random
                  ? "bg-emerald-600/20 text-emerald-300 ring-emerald-500/40"
                  : "bg-amber-600/20 text-amber-300 ring-amber-500/40"
              }`}
            >
              {pct(randomEntry.net_percentile_rank)} percentile
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt className="text-slate-500">Strategy net</dt>
              <dd className="font-mono text-slate-200 mt-0.5">{currency(randomEntry.strategy_net)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Threshold</dt>
              <dd className="font-mono text-slate-200 mt-0.5">{pct(randomEntry.threshold)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Long fraction</dt>
              <dd className="font-mono text-slate-200 mt-0.5">{pct(randomEntry.long_fraction)}</dd>
            </div>
          </div>
          {Object.keys(randomEntry.random_net_pctiles).length > 0 && (
            <>
              <p className="text-xs text-slate-500">Random-entry net distribution</p>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 text-xs">
                {Object.entries(randomEntry.random_net_pctiles)
                  .sort(([a], [b]) => Number(a) - Number(b))
                  .map(([k, v]) => (
                    <div key={k} className="text-center">
                      <div className="text-slate-500">p{k}</div>
                      <div className="font-mono text-slate-300">{currency(v)}</div>
                    </div>
                  ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
