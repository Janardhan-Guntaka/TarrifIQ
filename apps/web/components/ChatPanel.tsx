import type { ClassifyResponse, QueryHistoryItem } from "@/lib/api";

type ChatTurn = {
  id: string;
  query: string;
  country?: string | null;
  response?: ClassifyResponse | null;
  createdAt?: string;
};

export function historyToTurns(items: QueryHistoryItem[]): ChatTurn[] {
  return [...items]
    .reverse()
    .map((item) => ({
      id: item.id,
      query: item.raw_query,
      country: item.country,
      response: item.response_json ?? null,
      createdAt: item.created_at,
    }));
}

export function ChatMessage({ turn }: { turn: ChatTurn }) {
  const hts = turn.response?.classification?.hts_code;
  const duty = turn.response?.duty?.total_rate;
  const confidence = turn.response?.classification?.confidence_pct;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-brand px-4 py-3 text-sm text-white shadow-sm">
          <p>{turn.query}</p>
          {turn.country && (
            <p className="mt-1 text-xs text-blue-100">Origin: {turn.country}</p>
          )}
        </div>
      </div>
      {turn.response && (
        <div className="flex justify-start">
          <div
            className={`max-w-[90%] rounded-2xl rounded-bl-md border px-4 py-3 text-sm shadow-sm ${
              turn.response.meta?.off_topic
                ? "border-slate-200 bg-slate-50 text-slate-600"
                : "border-slate-200 bg-white"
            }`}
          >
            {turn.response.meta?.off_topic ? (
              <p className="leading-relaxed">{turn.response.explanation}</p>
            ) : (
              <>
            <div className="mb-2 flex flex-wrap gap-3 text-xs text-slate-500">
              {hts && (
                <span>
                  HTS <span className="font-mono font-semibold text-slate-900">{hts}</span>
                </span>
              )}
              {duty && <span className="font-semibold text-brand">Duty: {duty}</span>}
              {confidence != null && <span>{confidence}% confidence</span>}
            </div>
            {turn.response.explanation && (
              <p className="leading-relaxed text-slate-700">{turn.response.explanation}</p>
            )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function EmptyChat() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-4 text-center text-slate-500">
      <p className="text-sm font-medium text-slate-700">No classifications yet</p>
      <p className="mt-1 max-w-sm text-sm">
        Describe a product below — e.g. &quot;wireless earbuds from Vietnam, $45/unit&quot;
      </p>
    </div>
  );
}
