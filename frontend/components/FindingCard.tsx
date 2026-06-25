import type { Finding, VerdictStatus } from "@/lib/types";

const BADGE: Record<VerdictStatus, string> = {
  pass: "bg-emerald-600/20 text-emerald-300 ring-1 ring-emerald-500/40",
  caution: "bg-amber-600/20 text-amber-300 ring-1 ring-amber-500/40",
  fail: "bg-red-600/20 text-red-300 ring-1 ring-red-500/40",
  inconclusive: "bg-slate-600/20 text-slate-300 ring-1 ring-slate-500/40",
  info: "bg-blue-600/20 text-blue-300 ring-1 ring-blue-500/40",
};

const LABEL: Record<VerdictStatus, string> = {
  pass: "Pass",
  caution: "Caution",
  fail: "Fail",
  inconclusive: "Inconclusive",
  info: "Info",
};

export default function FindingCard({ finding }: { finding: Finding }) {
  return (
    <div className="rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-slate-200">{finding.title}</h3>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${BADGE[finding.status]}`}>
          {LABEL[finding.status]}
        </span>
      </div>
      <p className="text-sm text-slate-300">{finding.headline}</p>
      <p className="text-xs text-slate-500 leading-relaxed">{finding.detail}</p>
    </div>
  );
}
