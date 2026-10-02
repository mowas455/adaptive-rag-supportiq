import { useState } from "react";
import { pdfPreviewUrl } from "../api";
import type { ChatResponse, Citation } from "../types";

type Props = {
  response: ChatResponse | null;
};

export function EvidencePanel({ response }: Props) {
  const citations = response?.citations ?? [];
  const pdfCites = citations.filter((c) => c.page && c.source?.endsWith(".pdf"));
  const [activeId, setActiveId] = useState<number | null>(null);
  const selected: Citation | undefined =
    pdfCites.find((c) => c.id === activeId) ?? pdfCites[0];

  return (
    <section className="panel">
      <div className="panel-h">
        <h2>Evidence</h2>
        <p>Highlighted page the answer was grounded on. No coordinate dump.</p>
      </div>
      <div className="evidence">
        {pdfCites.length === 0 && (
          <div className="empty">
            {response
              ? "This turn did not retrieve a PDF (order lookup or web search)."
              : "Send a policy or hardware question to load a page."}
          </div>
        )}
        {pdfCites.length > 0 && (
          <div className="cite-list">
            {pdfCites.map((c) => (
              <button
                key={c.id}
                type="button"
                className={c.id === selected?.id ? "cite active" : "cite"}
                onClick={() => setActiveId(c.id)}
              >
                {c.source}
                <small>page {c.page}</small>
              </button>
            ))}
          </div>
        )}
        {selected?.source && selected.page && (
          <img
            className="preview"
            alt={`${selected.source} page ${selected.page}`}
            src={pdfPreviewUrl(selected.source, selected.page, selected.bbox)}
          />
        )}
      </div>
    </section>
  );
}
