"use client";

import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { currency } from "@/lib/format";

interface Props {
  curve: number[];
}

export default function EquityChart({ curve }: Props) {
  if (!curve.length) return null;

  const data = curve.map((v, i) => ({ trade: i + 1, equity: v }));
  const min = Math.min(...curve);
  const max = Math.max(...curve);
  const pad = (max - min) * 0.05 || 100;

  return (
    <div>
      <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
        Equity curve
      </h2>
      <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 h-52">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <XAxis
              dataKey="trade"
              tick={{ fill: "#64748b", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              label={{ value: "Trade #", position: "insideBottomRight", offset: -4, fill: "#64748b", fontSize: 10 }}
            />
            <YAxis
              tick={{ fill: "#64748b", fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => currency(v, 0)}
              domain={[min - pad, max + pad]}
              width={70}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1e293b",
                border: "1px solid #334155",
                borderRadius: "6px",
                fontSize: 12,
              }}
              labelStyle={{ color: "#94a3b8" }}
              formatter={(v: number) => [currency(v), "Equity"]}
              labelFormatter={(l: number) => `Trade ${l}`}
            />
            <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />
            <Line
              type="monotone"
              dataKey="equity"
              stroke="#6366f1"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
