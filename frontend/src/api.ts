import type { ChatResponse, HealthResponse, TraceDetail } from "./types";

const API = "/api";

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed (${res.status})`);
  }
  return res.json() as Promise<HealthResponse>;
}

export async function postChat(question: string, sessionId: string): Promise<ChatResponse> {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Chat failed (${res.status})`);
  }
  return res.json() as Promise<ChatResponse>;
}

export function pdfPreviewUrl(source: string, page: number, bbox?: {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
} | null): string {
  const params = new URLSearchParams({ source, page: String(page) });
  if (bbox) {
    params.set("x0", String(bbox.x0));
    params.set("y0", String(bbox.y0));
    params.set("x1", String(bbox.x1));
    params.set("y1", String(bbox.y1));
  }
  return `${API}/pdf-preview?${params.toString()}`;
}

export function traceIdFromResponse(response: ChatResponse): string | null {
  if (response.trace_id) return response.trace_id;
  if (!response.trace_url) return null;
  const match = response.trace_url.match(/trace[s]?\/([a-zA-Z0-9-]+)/);
  return match?.[1] ?? null;
}

export async function getTrace(traceId: string): Promise<TraceDetail> {
  const res = await fetch(`${API}/traces/${encodeURIComponent(traceId)}`);
  if (!res.ok) {
    throw new Error(`Trace fetch failed (${res.status})`);
  }
  return res.json() as Promise<TraceDetail>;
}
