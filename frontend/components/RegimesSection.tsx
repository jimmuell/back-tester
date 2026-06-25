import type { RegimeBreakdown } from "@/lib/types";
import { currency, pct, num } from "@/lib/format";

interface Props {
  regimes: Record<string, RegimeBreakdown>;
}

export default function RegimesSection({ regimes }: Props) {
  const entries = Object.entries(regimes);
  if (!entries.length) return null;

  return (
    <div className="space-y-4">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        Regime breakdown
      </h2>
      {entries.map(([key, rb]) => {
        const labels = Object.keys(rb.per_regime);
        return (
          <div
            key={key}
            className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-3"
          >
            <h3 className="text-sm font-medium text-slate-300 capitalize">{rb.scheme} regime</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-700">
                    <th className="pb-2 text-left font-medium">Regime</th>
                    <th className="pb-2 text-right font-medium">Trades</th>
                    <th className="pb-2 text-right font-medium">Win rate</th>
                    <th className="pb-2 text-right font-medium">Expectancy</th>
                    <th className="pb-2 text-right font-medium">Net profit</th>
                    <th className="pb-2 text-right font-medium">PF</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50 text-slate-300">
                  {labels.map((label) => {
                    const m = rb.per_regime[label];
                    return (
                      <tr key={label}>
                        <td className="py-1.5 text-slate-400 capitalize">{label}</td>
                        <td className="py-1.5 text-right font-mono">{m.total_trades}</td>
                        <td className="py-1.5 text-right font-mono">{pct(m.win_rate)}</td>
                        <td className="py-1.5 text-right font-mono">{currency(m.expectancy)}</td>
                        <td className="py-1.5 text-right font-mono">{currency(m.net_profit)}</td>
                        <td className="py-1.5 text-right font-mono">{num(m.profit_factor)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}
