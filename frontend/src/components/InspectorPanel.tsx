import { useEffect, useState } from "react";
import { getTrace, traceIdFromResponse } from "../api";
import type { ChatResponse, HealthResponse, TraceDetail } from "../types";

type Props = {
  response: ChatResponse | null;
  health: HealthResponse | null;
};

export function InspectorPanel({ response, health }: Props) {
  const [tab, setTab] = useState<"run" | "langfuse">("run");
  const [trace, setTrace] = useState<TraceDetail | null>(null);
  const [traceError, setTraceError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const traceId = response ? traceIdFromResponse(response) : null;
  const langfuseOk = health?.langfuse === true;

  useEffect(() => {
    if (tab !== "langfuse" || !traceId) {
      setTrace(null);
      setTraceError(null);
      return;
    }
    let alive = true;
    setLoading(true);
    setTraceError(null);
    getTrace(traceId)
      .then((detail) => {
        if (alive) setTrace(detail);
      })
      .catch((err: unknown) => {
        if (alive) {
          setTrace(null);
          setTraceError(err instanceof Error ? err.message : "Could not load trace");
        }
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [tab, traceId]);

  return (
    <section className="panel">
      <div className="panel-h">
        <h2>Observability</h2>
        <p>Same screen as chat: route, grades, and Langfuse.</p>
      </div>
      <div className="inspector">
        <div className="tabs">
          <button
            type="button"
            className={tab === "run" ? "active" : ""}
            onClick={() => setTab("run")}
          >
            This run
          </button>
          <button
            type="button"
            className={tab === "langfuse" ? "active" : ""}
            onClick={() => setTab("langfuse")}
          >
            Langfuse
          </button>
        </div>

        {tab === "run" && !response && (
          <div className="empty">Metrics appear after the first answer.</div>
        )}

        {tab === "run" && response && (
          <dl className="kv">
            <dt>route</dt>
            <dd>{response.route ?? response.source_type}</dd>
            <dt>source</dt>
            <dd>{response.source_type}</dd>
            <dt>router</dt>
            <dd>{response.router_backend ?? "—"}</dd>
            <dt>rationale</dt>
            <dd>{response.routing_rationale ?? "—"}</dd>
            <dt>search query</dt>
            <dd>{response.search_query ?? "—"}</dd>
            <dt>docs kept</dt>
            <dd>{response.docs_relevant_count}</dd>
            <dt>retries</dt>
            <dd>
              retrieve {response.retries} · regenerate {response.regenerate_count}
            </dd>
            <dt>grounded</dt>
            <dd>
              {response.groundedness_score == null
                ? "—"
                : response.groundedness_score === 1
                  ? "yes"
                  : "no"}
            </dd>
            <dt>citations</dt>
            <dd>{response.citations.length}</dd>
            <dt>trace</dt>
            <dd>{traceId ?? "—"}</dd>
            <dt>llama3.2</dt>
            <dd>
              {response.usage?.llm
                ? `${response.usage.llm.prompt_tokens} in / ${response.usage.llm.completion_tokens} out · ${response.usage.llm.total_tokens} total · ${response.usage.llm.calls} calls`
                : "—"}
            </dd>
            <dt>nomic-embed</dt>
            <dd>
              {response.usage?.embedding
                ? `${response.usage.embedding.prompt_tokens} tokens · ${response.usage.embedding.calls} calls`
                : "—"}
            </dd>
          </dl>
        )}

        {tab === "langfuse" && (
          <>
            <p className="empty">
              Langfuse’s own UI cannot be embedded (login + frame headers). We
              load the trace through our API instead.
              {langfuseOk ? " Langfuse is reachable." : " Langfuse is down."}
            </p>
            {response?.trace_url && (
              <p>
                <a
                  className="open-lf"
                  href={response.trace_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open full Langfuse UI
                </a>
              </p>
            )}
            {!traceId && <p className="empty">Ask a question to create a trace.</p>}
            {loading && <p className="empty">Loading graph steps…</p>}
            {traceError && <p className="err">{traceError}</p>}
            {trace && (
              <>
                <dl className="kv">
                  <dt>name</dt>
                  <dd>{trace.name ?? "—"}</dd>
                  <dt>session</dt>
                  <dd>{trace.session_id ?? "—"}</dd>
                  <dt>llama3.2 (this run)</dt>
                  <dd>
                    {response?.usage?.llm
                      ? `${response.usage.llm.prompt_tokens} in / ${response.usage.llm.completion_tokens} out`
                      : "—"}
                  </dd>
                  <dt>nomic-embed (this run)</dt>
                  <dd>
                    {response?.usage?.embedding
                      ? `${response.usage.embedding.prompt_tokens} tokens`
                      : "—"}
                  </dd>
                </dl>
                <h3 className="subh">Scores</h3>
                {trace.scores.length === 0 && <p className="empty">No scores yet.</p>}
                <ul className="obs-list">
                  {trace.scores.map((s) => (
                    <li key={`${s.name}-${String(s.value)}`}>
                      <strong>{s.name}</strong> {String(s.value ?? "—")}
                    </li>
                  ))}
                </ul>
                <h3 className="subh">Graph steps</h3>
                {trace.observations.length === 0 && (
                  <p className="empty">No observations on this trace.</p>
                )}
                <ol className="obs-list">
                  {trace.observations.map((obs) => (
                    <li key={obs.id ?? `${obs.name}-${obs.start_time}`}>
                      <strong>{obs.name}</strong>
                      <span>
                        {" "}
                        {obs.type}
                        {obs.model ? ` · ${obs.model}` : ""}
                        {obs.prompt_tokens || obs.completion_tokens
                          ? ` · ${obs.prompt_tokens ?? 0} in / ${obs.completion_tokens ?? 0} out`
                          : ""}
                      </span>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </>
        )}
      </div>
    </section>
  );
}
