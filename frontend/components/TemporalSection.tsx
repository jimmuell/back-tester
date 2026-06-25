import type { Split, WalkForward } from "@/lib/types";
import { currency, pct, num, shortDate } from "@/lib/format";

interface Props {
  split: Split | null;
  walkForward: WalkForward | null;
}

export default function TemporalSection({ split, walkForward }: Props) {
  if (!split && !walkForward) return null;

  return (
    <div className="space-y-4">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        Temporal stability
      </h2>

      {split && (
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-300">IS / OOS split</h3>
            {split.edge_decayed ? (
              <span className="text-xs rounded-full px-2 py-0.5 bg-red-600/20 text-red-300 ring-1 ring-red-500/40">
                Edge decayed
              </span>
            ) : (
              <span className="text-xs rounded-full px-2 py-0.5 bg-emerald-600/20 text-emerald-300 ring-1 ring-emerald-500/40">
                Edge held
              </span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-700">
                  <th className="pb-2 text-left font-medium">Period</th>
                  <th className="pb-2 text-right font-medium">Trades</th>
                  <th className="pb-2 text-right font-medium">Expectancy</th>
                  <th className="pb-2 text-right font-medium">Net profit</th>
                  <th className="pb-2 text-right font-medium">Win rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50 text-slate-300">
                <tr>
                  <td className="py-2 text-slate-400">In-sample</td>
                  <td className="py-2 text-right font-mono">{split.is_trades}</td>
                  <td className="py-2 text-right font-mono">{currency(split.is_expectancy)}</td>
                  <td className="py-2 text-right font-mono">{currency(split.is_net_profit)}</td>
                  <td className="py-2 text-right font-mono">{pct(split.is_win_rate)}</td>
                </tr>
                <tr>
                  <td className="py-2 text-slate-400">Out-of-sample</td>
                  <td className="py-2 text-right font-mono">{split.oos_trades}</td>
                  <td className="py-2 text-right font-mono">{currency(split.oos_expectancy)}</td>
                  <td className="py-2 text-right font-mono">{currency(split.oos_net_profit)}</td>
                  <td className="py-2 text-right font-mono">{pct(split.oos_win_rate)}</td>
                </tr>
              </tbody>
            </table>
          </div>
          {split.expectancy_ratio != null && (
            <p className="text-xs text-slate-500">
              IS→OOS expectancy ratio: {num(split.expectancy_ratio)}×
              {" · "}Split at {shortDate(split.split_time)}
            </p>
          )}
        </div>
      )}

      {walkForward && (
        <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-300">
              Walk-forward ({walkForward.n_windows} windows, {walkForward.scheme})
            </h3>
            <span className="text-xs font-mono text-slate-400">
              {pct(walkForward.pct_windows_positive)} positive
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <dt className="text-slate-500">Mean expectancy</dt>
              <dd className="font-mono text-slate-200 mt-0.5">{currency(walkForward.expectancy_mean)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Std dev</dt>
              <dd className="font-mono text-slate-200 mt-0.5">{currency(walkForward.expectancy_std)}</dd>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-700">
                  <th className="pb-2 text-left font-medium">Window</th>
                  <th className="pb-2 text-right font-medium">Trades</th>
                  <th className="pb-2 text-right font-medium">Expectancy</th>
                  <th className="pb-2 text-right font-medium">Net profit</th>
                  <th className="pb-2 text-right font-medium">Win rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {walkForward.windows.map((w) => (
                  <tr key={w.index} className={w.net_profit >= 0 ? "text-slate-300" : "text-red-400"}>
                    <td className="py-1.5 text-slate-400">{w.index + 1}</td>
                    <td className="py-1.5 text-right font-mono">{w.n_trades}</td>
                    <td className="py-1.5 text-right font-mono">{currency(w.expectancy)}</td>
                    <td className="py-1.5 text-right font-mono">{currency(w.net_profit)}</td>
                    <td className="py-1.5 text-right font-mono">{pct(w.win_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
