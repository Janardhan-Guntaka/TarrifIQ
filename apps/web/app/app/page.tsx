"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import {
  classify,
  listQueries,
  type ClassifyResponse,
  type QueryHistoryItem,
} from "@/lib/api";
import { ChatMessage, EmptyChat, historyToTurns } from "@/components/ChatPanel";
import { Disclaimer } from "@/components/Disclaimer";
import { APP_NAME } from "@/lib/constants";

export default function AppPage() {
  const [email, setEmail] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [history, setHistory] = useState<QueryHistoryItem[]>([]);
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState("");
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadHistory = useCallback(async (accessToken: string) => {
    setRefreshing(true);
    try {
      const rows = await listQueries(accessToken);
      setHistory(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        window.location.href = "/login";
        return;
      }
      setEmail(session.user.email ?? "");
      setToken(session.access_token);
      loadHistory(session.access_token);
    });
  }, [loadHistory]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, loading]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !query.trim()) return;
    setLoading(true);
    setError("");
    const optimisticQuery = query.trim();
    setQuery("");

    try {
      const res: ClassifyResponse = await classify(
        {
          query: optimisticQuery,
          country: country || undefined,
          customs_value: value ? parseFloat(value) : undefined,
        },
        token
      );
      const newItem: QueryHistoryItem = {
        id: res.query_id ?? crypto.randomUUID(),
        raw_query: optimisticQuery,
        country: country || null,
        selected_hts_code: res.classification?.hts_code ?? null,
        response_json: res,
        created_at: new Date().toISOString(),
      };
      setHistory((prev) => [newItem, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setQuery(optimisticQuery);
    } finally {
      setLoading(false);
    }
  }

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    window.location.href = "/";
  }

  const turns = historyToTurns(history);

  return (
    <div className="flex h-screen flex-col bg-slate-100">
      <header className="flex shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-xs font-bold text-white">
              TQ
            </span>
            <span className="font-semibold text-slate-900">{APP_NAME}</span>
          </Link>
          <span className="hidden text-xs text-slate-400 sm:inline">|</span>
          <span className="hidden truncate text-xs text-slate-500 sm:inline">{email}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => token && loadHistory(token)}
            disabled={refreshing}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
          <button
            type="button"
            onClick={signOut}
            className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="shrink-0 border-b border-amber-100 bg-amber-50/80 px-4 py-2 sm:px-6">
        <p className="text-xs text-amber-900">
          <span className="font-medium">Early access — </span>
          Cross-check all HTS codes and duties with official USITC/CBP documents before filing.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {turns.length === 0 && !loading ? (
            <EmptyChat />
          ) : (
            turns.map((turn) => <ChatMessage key={turn.id} turn={turn} />)
          )}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
                Classifying product…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {error && (
        <div className="mx-4 mb-2 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800 sm:mx-6">
          {error}
        </div>
      )}

      <form
        onSubmit={onSubmit}
        className="shrink-0 border-t border-slate-200 bg-white px-4 py-4 sm:px-6"
      >
        <div className="mx-auto max-w-3xl space-y-3">
          <textarea
            className="w-full resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
            rows={2}
            placeholder="Describe your product — e.g. stainless steel water bottles from China, $8/unit"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={loading}
          />
          <div className="flex flex-wrap items-end gap-3">
            <input
              className="min-w-[140px] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="Country of origin"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              disabled={loading}
            />
            <input
              type="number"
              min="0"
              className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="Value USD"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="rounded-lg bg-brand px-5 py-2 text-sm font-semibold text-white hover:bg-brand-dark disabled:opacity-50"
            >
              Classify
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
