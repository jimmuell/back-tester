interface Props {
  skipped: string[];
}

export default function SkippedNote({ skipped }: Props) {
  if (!skipped.length) return null;

  return (
    <div className="rounded-lg border border-amber-700/30 bg-amber-950/20 p-4 space-y-2">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-amber-400">
        Skipped analyses
      </h2>
      <ul className="space-y-1">
        {skipped.map((msg, i) => (
          <li key={i} className="text-xs text-amber-300/80 font-mono">
            • {msg}
          </li>
        ))}
      </ul>
    </div>
  );
}
