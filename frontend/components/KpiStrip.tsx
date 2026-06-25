import type { Metrics, Bootstrap } from "@/lib/types";
import { currency, pct, num } from "@/lib/format";

interface Props {
  metrics: Metrics;
  bootstrap: Bootstrap;
}

export default function KpiStrip({ metrics, bootstrap }: Props) {
  const ci = bootstrap.ci_level * 100;
  const [expLo, expHi] = bootstrap.expectancy_ci;

  const items = [
    { label: "Net profit", value: currency(metrics.net_profit) },
    { label: "Trades", value: String(metrics.total_trades) },
    { label: "Win rate", value: pct(metrics.win_rate) },
    { label: "Expectancy", value: currency(metrics.expectancy) },
    { label: `${ci}% CI`, value: `${currency(expLo)} – ${currency(expHi)}` },
    { label: "Profit factor", value: num(metrics.profit_factor) },
    { label: "Max drawdown", value: currency(metrics.max_drawdown) },
    { label: "Avg win", value: currency(metrics.avg_win) },
    { label: "Avg loss", value: currency(metrics.avg_loss) },
    { label: "Payoff ratio", value: num(metrics.payoff_ratio) },
    { label: "Win streak", value: String(metrics.longest_win_streak) },
    { label: "Loss streak", value: String(metrics.longest_loss_streak) },
  ];

  return (
    <div>
      <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
        Key metrics
      </h2>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {items.map(({ label, value }) => (
          <div key={label} className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-3">
            <dt className="text-xs text-slate-500 truncate">{label}</dt>
            <dd className="mt-1 text-sm font-mono font-medium text-slate-200 truncate">{value}</dd>
          </div>
        ))}
      </div>
    </div>
  );
}
