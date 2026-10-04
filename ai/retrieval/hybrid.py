"""Hybrid retrieval: dense + lexical fused with RRF (backend-agnostic)."""

from __future__ import annotations

from collections import defaultdict

from ai.config import RETRIEVE_K
from ai.graph.state import RetrievedDoc
from ai.ingestion.pdf_extract import parse_layout

DOC_TYPE_HINTS: dict[str, tuple[str, ...]] = {
    "policy": ("return", "refund", "exchange", "warranty", "final sale"),
    "shipping": ("ship", "po box", "apo", "tracking", "delivery delay", "overnight"),
    "troubleshooting": (
        "pair",
        "pulsebuds",
        "homeplug",
        "lockstep",
        "flicker",
        "firmware",
        "won't",
        "will not",
    ),
    "billing": ("plus", "invoice", "billing", "gift card", "chargeback", "payment"),
    "product": ("glowbar", "install", "matter", "led strip", "adhesive"),
}


def _hint_types(query: str) -> set[str]:
    q = query.lower()
    return {dtype for dtype, words in DOC_TYPE_HINTS.items() if any(w in q for w in words)}


def _to_retrieved(content: str, metadata: dict) -> RetrievedDoc:
    layout = parse_layout(metadata)
    doc: RetrievedDoc = {
        "content": content,
        "source": str(metadata.get("source_file") or metadata.get("source") or "vectorstore"),
        "chunk_index": int(metadata.get("chunk_index") or 0),
        "doc_type": str(metadata.get("doc_type") or "unknown"),
    }
    if layout.get("page") is not None:
        doc["page"] = int(layout["page"])
    if layout.get("page_width") is not None:
        doc["page_width"] = float(layout["page_width"])
    if layout.get("page_height") is not None:
        doc["page_height"] = float(layout["page_height"])
    if layout.get("bbox"):
        doc["bbox"] = layout["bbox"]
    if layout.get("polygon"):
        doc["polygon"] = layout["polygon"]
    if layout.get("polygon_norm"):
        doc["polygon_norm"] = layout["polygon_norm"]
    if layout.get("extraction"):
        doc["extraction"] = str(layout["extraction"])
    return doc


def hybrid_search(index, query: str, *, k: int = RETRIEVE_K) -> list[RetrievedDoc]:
    """RRF of dense neighbors and lexical hits (BM25 on Chroma, FTS on Supabase)."""
    fetch = max(k * 2, 8)
    dense = index.similarity_search(query, k=fetch)
    lexical = index.lexical_search(query, k=fetch)
    if not dense and not lexical:
        return []

    rrf: dict[str, float] = defaultdict(float)
    payload: dict[str, tuple[str, dict]] = {}
    hints = _hint_types(query)

    def _key(content: str, meta: dict) -> str:
        return f"{meta.get('source_file')}:{meta.get('chunk_index')}:{hash(content) % 10_000}"

    for rank, (content, meta) in enumerate(dense):
        key = _key(content, meta)
        payload[key] = (content, dict(meta))
        rrf[key] += 1.0 / (60 + rank)

    for rank, (content, meta) in enumerate(lexical):
        key = _key(content, meta)
        payload[key] = (content, dict(meta))
        rrf[key] += 1.0 / (60 + rank)

    for key, (_, meta) in payload.items():
        if hints and meta.get("doc_type") in hints:
            rrf[key] += 0.15

    ranked = sorted(rrf, key=lambda item: rrf[item], reverse=True)
    out: list[RetrievedDoc] = []
    seen = set()
    for key in ranked:
        content, meta = payload[key]
        if content in seen:
            continue
        seen.add(content)
        out.append(_to_retrieved(content, meta))
        if len(out) >= k:
            break
    return out
