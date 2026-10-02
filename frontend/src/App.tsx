import { useEffect, useMemo, useState } from "react";
import { getHealth, postChat } from "./api";
import { ChatPanel } from "./components/ChatPanel";
import { EvidencePanel } from "./components/EvidencePanel";
import { InspectorPanel } from "./components/InspectorPanel";
import { TopBar } from "./components/TopBar";
import type { ChatMessage, ChatResponse, HealthResponse } from "./types";

function newId(): string {
  return crypto.randomUUID();
}

export default function App() {
  const sessionId = useMemo(() => newId(), []);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () => {
      getHealth()
        .then((h) => {
          if (alive) setHealth(h);
        })
        .catch(() => {
          if (alive) setHealth(null);
        });
    };
    tick();
    const id = window.setInterval(tick, 8000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  const selected: ChatResponse | null =
    messages.find((m) => m.id === selectedId)?.response ??
    [...messages].reverse().find((m) => m.response)?.response ??
    null;

  async function onSend(text: string) {
    setError(null);
    setMessages((prev) => [...prev, { id: newId(), role: "user", content: text }]);
    setBusy(true);
    try {
      const response = await postChat(text, sessionId);
      const id = newId();
      setMessages((prev) => [
        ...prev,
        { id, role: "assistant", content: response.answer, response },
      ]);
      setSelectedId(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <TopBar health={health} />
      <div className="workspace">
        <ChatPanel
          messages={messages}
          busy={busy}
          error={error}
          onSend={onSend}
          onSelect={setSelectedId}
          selectedId={selectedId}
        />
        <EvidencePanel response={selected} />
        <InspectorPanel response={selected} health={health} />
      </div>
    </div>
  );
}
