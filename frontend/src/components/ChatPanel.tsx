import { useState } from "react";
import type { ChatMessage } from "../types";

type Props = {
  messages: ChatMessage[];
  busy: boolean;
  error: string | null;
  onSend: (text: string) => void;
  onSelect: (id: string) => void;
  selectedId: string | null;
};

function badgeClass(route: string | undefined): string {
  if (route === "web_search") return "badge web";
  if (route === "sql_lookup") return "badge sql";
  return "badge";
}

export function ChatPanel({ messages, busy, error, onSend, onSelect, selectedId }: Props) {
  const [draft, setDraft] = useState("");

  function submit() {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    onSend(text);
  }

  return (
    <section className="panel">
      <div className="panel-h">
        <h2>Conversation</h2>
        <p>Customer-facing answer. Route is decided before generation.</p>
      </div>
      <div className="messages">
        {messages.length === 0 && (
          <div className="empty">
            Ask a policy, hardware, order, or live-ops question. Evidence and the
            run inspector update from the same response.
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`bubble ${msg.role}`}
            onClick={() => msg.role === "assistant" && onSelect(msg.id)}
            style={
              msg.role === "assistant" && msg.id === selectedId
                ? { outline: "2px solid #0e7c7b" }
                : undefined
            }
          >
            {msg.content}
            {msg.response && (
              <div className="meta">
                <span className={badgeClass(msg.response.source_type)}>
                  {msg.response.source_type}
                </span>
                {msg.response.retries > 0 && <span className="badge">retry</span>}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="empty">Routing and generating…</div>}
      </div>
      {error && <div className="err">{error}</div>}
      <div className="composer">
        <textarea
          value={draft}
          placeholder="What's your return window?"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button type="button" disabled={busy} onClick={submit}>
          Send
        </button>
      </div>
    </section>
  );
}
