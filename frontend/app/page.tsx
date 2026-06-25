"use client";

import { useState } from "react";
import { validate, ApiError } from "@/lib/api";
import type { ValidationResponse } from "@/lib/types";
import UploadForm from "@/components/UploadForm";
import VerdictHero from "@/components/VerdictHero";
import FindingCard from "@/components/FindingCard";
import KpiStrip from "@/components/KpiStrip";
import EquityChart from "@/components/EquityChart";
import MonteCarloSection from "@/components/MonteCarloSection";
import TemporalSection from "@/components/TemporalSection";
import BenchmarksSection from "@/components/BenchmarksSection";
import RegimesSection from "@/components/RegimesSection";
import SkippedNote from "@/components/SkippedNote";

const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME ?? "BackTester";

export default function ValidatorPage() {
  const [result, setResult] = useState<ValidationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(trades: File, bars: File | null) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await validate(trades, bars);
      setResult(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl space-y-8">
        {/* Header */}
        <header className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">{APP_NAME}</h1>
          <p className="text-sm text-slate-400">
            Upload a TradingView trade list to validate your strategy's statistical edge.
          </p>
        </header>

        {/* Upload */}
        <section className="rounded-xl border border-slate-700/60 bg-slate-800/30 p-6 space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Upload
          </h2>
          <UploadForm onSubmit={handleSubmit} loading={loading} />
        </section>

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-red-700/40 bg-red-950/20 p-4 text-sm text-red-300">
            <span className="font-semibold">Error: </span>{error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center gap-3 text-sm text-slate-400 py-4">
            <svg
              className="h-4 w-4 animate-spin text-indigo-400"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            Running Monte Carlo validation — this takes a few seconds…
          </div>
        )}

        {/* Results */}
        {result && <Results result={result} />}
      </div>
    </div>
  );
}

function Results({ result }: { result: ValidationResponse }) {
  return (
    <div className="space-y-6">
      {/* Verdict hero */}
      <VerdictHero verdict={result.verdict} />

      {/* Findings */}
      <div className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Findings
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {result.verdict.findings.map((f) => (
            <FindingCard key={f.key} finding={f} />
          ))}
        </div>
      </div>

      {/* KPI strip */}
      <KpiStrip metrics={result.metrics} bootstrap={result.bootstrap} />

      {/* Equity curve */}
      <EquityChart curve={result.metrics.equity_curve} />

      {/* Monte Carlo */}
      <MonteCarloSection bootstrap={result.bootstrap} shuffle={result.shuffle} />

      {/* Temporal */}
      <TemporalSection split={result.split} walkForward={result.walk_forward} />

      {/* Benchmarks */}
      <BenchmarksSection buyHold={result.buy_hold} randomEntry={result.random_entry} />

      {/* Regimes */}
      <RegimesSection regimes={result.regimes} />

      {/* Skipped */}
      <SkippedNote skipped={result.skipped} />
    </div>
  );
}
