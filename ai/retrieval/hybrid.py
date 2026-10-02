"""Hybrid retrieval: dense Chroma search fused with BM25 (RRF)."""

from __future__ import annotations

import re
from collections import defaultdict

from rank_bm25 import BM25Okapi

from ai.config import RETRIEVE_K
from ai.graph.state import RetrievedDoc
from ai.ingestion.pdf_extract import parse_layout

_TOKEN = re.compile(r"[a-z0-9]+")

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


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


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


def hybrid_search(vectorstore, query: str, *, k: int = RETRIEVE_K) -> list[RetrievedDoc]:
    """Reciprocal-rank fusion of vector neighbors and BM25 over the full collection."""
    fetch = max(k * 2, 8)
    dense = vectorstore.similarity_search(query, k=fetch)

    raw = vectorstore._collection.get(include=["documents", "metadatas"])  # noqa: SLF001
    corpus = list(raw.get("documents") or [])
    metadatas = list(raw.get("metadatas") or [])
    if not corpus:
        return [_to_retrieved(d.page_content, d.metadata) for d in dense[:k]]

    tokenized = [_tokens(doc) for doc in corpus]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(_tokens(query))
    bm25_ranked = sorted(range(len(corpus)), key=lambda i: float(scores[i]), reverse=True)[:fetch]

    rrf: dict[str, float] = defaultdict(float)
    payload: dict[str, tuple[str, dict]] = {}
    hints = _hint_types(query)

    def _key(content: str, meta: dict) -> str:
        return f"{meta.get('source_file')}:{meta.get('chunk_index')}:{hash(content) % 10_000}"

    for rank, doc in enumerate(dense):
        key = _key(doc.page_content, doc.metadata)
        payload[key] = (doc.page_content, dict(doc.metadata))
        rrf[key] += 1.0 / (60 + rank)

    for rank, idx in enumerate(bm25_ranked):
        meta = dict(metadatas[idx] or {})
        content = corpus[idx]
        key = _key(content, meta)
        payload[key] = (content, meta)
        rrf[key] += 1.0 / (60 + rank)

    for key, (_, meta) in payload.items():
        if hints and meta.get("doc_type") in hints:
            rrf[key] += 0.15

    ranked = sorted(rrf, key=lambda k: rrf[k], reverse=True)
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
