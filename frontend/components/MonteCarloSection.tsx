import type { Bootstrap, Shuffle } from "@/lib/types";
import { currency, pct, num } from "@/lib/format";

interface Props {
  bootstrap: Bootstrap;
  shuffle: Shuffle;
}

export default function MonteCarloSection({ bootstrap, shuffle }: Props) {
  const ciPct = `${(bootstrap.ci_level * 100).toFixed(0)}%`;
  const ddPctiles = Object.entries(shuffle.max_drawdown_pctiles).sort(
    ([a], [b]) => Number(a) - Number(b),
  );

  return (
    <div className="space-y-4">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        Monte Carlo
      </h2>

      <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-3">
        <h3 className="text-sm font-medium text-slate-300">
          Bootstrap ({bootstrap.n_iterations.toLocaleString()} iterations)
        </h3>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-slate-700">
              <th className="pb-2 text-left font-medium">Metric</th>
              <th className="pb-2 text-right font-medium">Point</th>
              <th className="pb-2 text-right font-medium">{ciPct} CI</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            <TRow
              label="Expectancy"
              point={currency(bootstrap.expectancy_point)}
              ci={`${currency(bootstrap.expectancy_ci[0])} – ${currency(bootstrap.expectancy_ci[1])}`}
            />
            <TRow
              label="Net profit"
              point={currency(bootstrap.net_profit_point)}
              ci={`${currency(bootstrap.net_profit_ci[0])} – ${currency(bootstrap.net_profit_ci[1])}`}
            />
            <TRow
              label="Win rate"
              point={pct(bootstrap.win_rate_point)}
              ci={`${pct(bootstrap.win_rate_ci[0])} – ${pct(bootstrap.win_rate_ci[1])}`}
            />
            <TRow
              label="Profit factor"
              point={num(bootstrap.profit_factor_point)}
              ci={
                bootstrap.profit_factor_ci[0] != null && bootstrap.profit_factor_ci[1] != null
                  ? `${num(bootstrap.profit_factor_ci[0])} – ${num(bootstrap.profit_factor_ci[1])}`
                  : "—"
              }
            />
          </tbody>
        </table>
        {bootstrap.n_inf_pf > 0 && (
          <p className="text-xs text-slate-500">
            {bootstrap.n_inf_pf.toLocaleString()} samples had no losing trades (infinite profit factor).
          </p>
        )}
      </div>

      <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-3">
        <h3 className="text-sm font-medium text-slate-300">
          Trade-order shuffle ({shuffle.n_iterations.toLocaleString()} iterations)
        </h3>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <Stat label="Risk of ruin" value={pct(shuffle.risk_of_ruin)} />
          <Stat label="Ruin threshold" value={currency(shuffle.ruin_threshold)} />
        </div>
        {ddPctiles.length > 0 && (
          <>
            <p className="text-xs text-slate-500">Max drawdown distribution</p>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 text-xs">
              {ddPctiles.map(([k, v]) => (
                <div key={k} className="text-center">
                  <div className="text-slate-500">p{k}</div>
                  <div className="font-mono text-slate-300">{currency(v)}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function TRow({ label, point, ci }: { label: string; point: string; ci: string }) {
  return (
    <tr className="text-slate-300">
      <td className="py-2 text-slate-400">{label}</td>
      <td className="py-2 text-right font-mono">{point}</td>
      <td className="py-2 text-right font-mono text-slate-400">{ci}</td>
    </tr>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-mono text-slate-200 mt-0.5">{value}</dd>
    </div>
  );
}
