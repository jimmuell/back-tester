"use client";

import { useRef, useState } from "react";

interface Props {
  onSubmit: (trades: File, bars: File | null) => void;
  loading: boolean;
}

export default function UploadForm({ onSubmit, loading }: Props) {
  const tradesRef = useRef<HTMLInputElement>(null);
  const barsRef = useRef<HTMLInputElement>(null);
  const [tradesName, setTradesName] = useState<string>("");
  const [barsName, setBarsName] = useState<string>("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const tradesFile = tradesRef.current?.files?.[0];
    if (!tradesFile) return;
    const barsFile = barsRef.current?.files?.[0] ?? null;
    onSubmit(tradesFile, barsFile);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <FileInput
          label="Trade list (required)"
          hint="TradingView List of Trades CSV"
          accept=".csv"
          inputRef={tradesRef}
          fileName={tradesName}
          onChange={setTradesName}
          required
        />
        <FileInput
          label="Bar data (optional)"
          hint="FirstRate ES daily CSV — enables benchmarks & regime analysis"
          accept=".csv"
          inputRef={barsRef}
          fileName={barsName}
          onChange={setBarsName}
        />
      </div>
      <button
        type="submit"
        disabled={loading || !tradesName}
        className="w-full rounded-lg bg-indigo-600 px-6 py-3 text-sm font-semibold text-white
                   hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50
                   transition-colors duration-150"
      >
        {loading ? "Validating…" : "Validate strategy"}
      </button>
    </form>
  );
}

function FileInput({
  label,
  hint,
  accept,
  inputRef,
  fileName,
  onChange,
  required,
}: {
  label: string;
  hint: string;
  accept: string;
  inputRef: React.RefObject<HTMLInputElement>;
  fileName: string;
  onChange: (name: string) => void;
  required?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1 cursor-pointer">
      <span className="text-xs font-medium text-slate-400 uppercase tracking-wide">{label}</span>
      <div
        className="flex items-center gap-3 rounded-lg border border-slate-700 bg-slate-800/60
                      px-4 py-3 text-sm hover:border-indigo-500 transition-colors"
      >
        <svg
          className="h-4 w-4 shrink-0 text-slate-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0
               01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <span className={fileName ? "text-slate-200 truncate" : "text-slate-500 truncate"}>
          {fileName || "Choose file…"}
        </span>
      </div>
      <span className="text-xs text-slate-500">{hint}</span>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        required={required}
        className="sr-only"
        onChange={(e) => onChange(e.target.files?.[0]?.name ?? "")}
      />
    </label>
  );
}
