export type RouteName = "vectorstore" | "sql_lookup" | "web_search" | string;

export type BBox = {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
};

export type Citation = {
  id: number;
  source: string | null;
  doc_type: string | null;
  chunk_index: number | null;
  snippet: string;
  page: number | null;
  page_width: number | null;
  page_height: number | null;
  bbox: BBox | null;
  extraction: string | null;
};

export type ChatResponse = {
  answer: string;
  source_type: string;
  retries: number;
  trace_url: string | null;
  route: string | null;
  regenerate_count: number;
  groundedness_score: number | null;
  citations: Citation[];
  router_backend: string | null;
  routing_rationale: string | null;
  search_query: string | null;
  docs_relevant_count: number;
  trace_id: string | null;
  usage?: {
    llm: {
      model: string;
      prompt_tokens: number;
      completion_tokens: number;
      total_tokens: number;
      calls: number;
    };
    embedding: {
      model: string;
      prompt_tokens: number;
      calls: number;
    };
  } | null;
};

export type TraceScore = {
  name: string | null;
  value: string | number | boolean | null;
  data_type: string | null;
};

export type TraceObservation = {
  id: string | null;
  name: string | null;
  type: string | null;
  start_time: string | null;
  end_time: string | null;
  model: string | null;
  level: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
};

export type TraceDetail = {
  id: string;
  name: string | null;
  session_id: string | null;
  timestamp: string | null;
  html_path: string;
  scores: TraceScore[];
  observations: TraceObservation[];
};

export type HealthResponse = {
  status: string;
  ollama: boolean;
  chroma: boolean;
  langfuse: boolean;
  details: Record<string, unknown>;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
};
