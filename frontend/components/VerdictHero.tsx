import type { Verdict, VerdictStatus } from "@/lib/types";

const STATUS_STYLES: Record<VerdictStatus, { ring: string; badge: string; label: string }> = {
  pass: {
    ring: "ring-emerald-500/40 bg-emerald-950/30",
    badge: "bg-emerald-600/20 text-emerald-300 ring-1 ring-emerald-500/40",
    label: "Promising",
  },
  caution: {
    ring: "ring-amber-500/40 bg-amber-950/20",
    badge: "bg-amber-600/20 text-amber-300 ring-1 ring-amber-500/40",
    label: "Caution",
  },
  fail: {
    ring: "ring-red-500/40 bg-red-950/20",
    badge: "bg-red-600/20 text-red-300 ring-1 ring-red-500/40",
    label: "Failed",
  },
  inconclusive: {
    ring: "ring-slate-500/40 bg-slate-800/40",
    badge: "bg-slate-600/20 text-slate-300 ring-1 ring-slate-500/40",
    label: "Inconclusive",
  },
  info: {
    ring: "ring-blue-500/40 bg-blue-950/20",
    badge: "bg-blue-600/20 text-blue-300 ring-1 ring-blue-500/40",
    label: "Info",
  },
};

export default function VerdictHero({ verdict }: { verdict: Verdict }) {
  const s = STATUS_STYLES[verdict.overall];
  return (
    <div className={`rounded-xl p-6 ring-1 ${s.ring}`}>
      <div className="flex items-center gap-3 mb-3">
        <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider ${s.badge}`}>
          {s.label}
        </span>
        <span className="text-xs text-slate-500">Overall verdict</span>
      </div>
      <p className="text-slate-200 text-sm leading-relaxed">{verdict.summary}</p>
    </div>
  );
}
