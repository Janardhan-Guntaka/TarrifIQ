"use client";

import { useState } from "react";
import { classify, healthCheck, type ClassifyResponse } from "@/lib/api";

export default function Home() {
  const [query, setQuery] = useState("gaming laptop from China");
  const [country, setCountry] = useState("China");
  const [value, setValue] = useState("1200");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ClassifyResponse | null>(null);
  const [health, setHealth] = useState<string>("");

  async function onCheckHealth() {
    try {
      const h = await healthCheck();
      setHealth(JSON.stringify(h, null, 2));
    } catch (e) {
      setHealth(String(e));
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await classify({
        query,
        country: country || undefined,
        customs_value: value ? parseFloat(value) : undefined,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-3xl px-4 py-10">
      <header className="mb-10">
        <p className="text-sm font-medium uppercase tracking-wide text-brand">TariffIQ</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">US Import Duty Calculator</h1>
        <p className="mt-2 text-slate-600">
          Classify products into HTS codes and estimate duties with explainable results.
        </p>
      </header>

      <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <label className="mb-1 block text-sm font-medium">Product description</label>
          <textarea
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
            rows={3}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            required
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium">Country of origin</label>
            <input
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Customs value (USD)</label>
            <input
              type="number"
              min="0"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
          >
            {loading ? "Classifying…" : "Classify & estimate duty"}
          </button>
          <button
            type="button"
            onClick={onCheckHealth}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Check API health
          </button>
        </div>
      </form>

      {error && (
        <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>
      )}

      {health && (
        <pre className="mt-6 overflow-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">{health}</pre>
      )}

      {result && (
        <section className="mt-8 space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold">Classification</h2>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-slate-500">HTS Code</dt>
                <dd className="font-mono text-lg font-semibold">{result.classification?.hts_code || "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Confidence</dt>
                <dd>{result.classification?.confidence_pct ?? "—"}%</dd>
              </div>
              <div>
                <dt className="text-slate-500">Release</dt>
                <dd>{result.release_version || "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Total duty</dt>
                <dd className="text-lg font-semibold text-brand">{result.duty?.total_rate || "—"}</dd>
              </div>
            </dl>
            {result.duty?.duty_usd != null && (
              <p className="mt-3 text-sm text-slate-600">Estimated duty: ${result.duty.duty_usd.toLocaleString()}</p>
            )}
          </div>

          {result.explanation && (
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold">Explanation</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-700">{result.explanation}</p>
            </div>
          )}

          {result.disclaimer && (
            <p className="text-xs text-slate-500">{result.disclaimer}</p>
          )}
        </section>
      )}
    </main>
  );
}
