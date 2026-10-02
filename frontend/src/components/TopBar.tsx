import type { HealthResponse } from "../types";

type Props = {
  health: HealthResponse | null;
};

export function TopBar({ health }: Props) {
  const pill = (ok: boolean | undefined, label: string) => (
    <span className={ok ? "pill on" : "pill off"}>{label}</span>
  );

  return (
    <header className="topbar">
      <div className="brand">
        <strong>NEXCART SUPPORTIQ</strong>
        <span>Adaptive RAG console · policy · orders · live web</span>
      </div>
      <div className="pills">
        {pill(health?.status === "ok", health?.status ?? "api")}
        {pill(health?.ollama, "ollama")}
        {pill(health?.chroma, "chroma")}
        {pill(health?.langfuse, "langfuse")}
      </div>
    </header>
  );
}
