const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type ClassifyRequest = {
  query: string;
  country?: string;
  customs_value?: number;
};

export type ClassifyResponse = {
  query_id?: string;
  release_version?: string;
  policy_version?: string;
  classification?: {
    hts_code?: string;
    heading?: string;
    confidence_pct?: number;
    origin_country?: string;
    reasoning?: string;
    escalate?: boolean;
    escalate_reason?: string;
  };
  duty?: {
    total_rate?: string;
    applicable_rate?: string;
    duty_usd?: number | null;
    section_301?: boolean;
    ieepa?: boolean;
  };
  explanation?: string;
  disclaimer?: string;
  meta?: { latency_ms?: number; off_topic?: boolean };
};

export type QueryHistoryItem = {
  id: string;
  raw_query: string;
  country?: string | null;
  selected_hts_code?: string | null;
  confidence?: number | null;
  hts_release?: string | null;
  latency_ms?: number | null;
  escalate?: boolean;
  created_at?: string;
  response_json?: ClassifyResponse | null;
};

function authHeaders(token?: string): HeadersInit {
  const h: HeadersInit = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export async function classify(
  body: ClassifyRequest,
  accessToken?: string
): Promise<ClassifyResponse> {
  const res = await fetch(`${API}/v1/classify`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `API error ${res.status}`);
  }
  return res.json();
}

export async function listQueries(accessToken: string): Promise<QueryHistoryItem[]> {
  const res = await fetch(`${API}/v1/queries?limit=50`, {
    headers: authHeaders(accessToken),
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `API error ${res.status}`);
  }
  return res.json();
}

export async function healthCheck(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API}/health`, { cache: "no-store" });
  return res.json();
}
