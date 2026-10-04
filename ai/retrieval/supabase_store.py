"""Supabase pgvector index. Uses URL + service_role key (never the anon key)."""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document

from ai.config import (
    SUPABASE_CHUNKS_TABLE,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)
from ai.observability.usage import tracked_embeddings
from ai.retrieval.store import Hit


def _client():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "VECTOR_BACKEND=supabase needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
            "in .env (Project Settings → API → service_role). Do not use the anon key."
        )
    from supabase import create_client

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _bbox_json(meta: dict) -> dict | None:
    keys = ("bbox_x0", "bbox_y0", "bbox_x1", "bbox_y1")
    if not all(meta.get(k) is not None for k in keys):
        return None
    return {
        "x0": float(meta["bbox_x0"]),
        "y0": float(meta["bbox_y0"]),
        "x1": float(meta["bbox_x1"]),
        "y1": float(meta["bbox_y1"]),
    }


def _jsonish(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    import json

    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _row_to_meta(row: dict) -> dict:
    bbox = _jsonish(row.get("bbox")) or {}
    meta = {
        "source_file": row.get("source_file"),
        "source": row.get("source_file"),
        "doc_type": row.get("doc_type") or "unknown",
        "chunk_index": row.get("chunk_index") or 0,
        "page": row.get("page"),
        "page_width": row.get("page_width"),
        "page_height": row.get("page_height"),
        "polygon": row.get("polygon") or "[]",
        "polygon_norm": row.get("polygon_norm") or "[]",
        "extraction": row.get("extraction"),
        "bbox": bbox,
    }
    if isinstance(bbox, dict):
        meta["bbox_x0"] = bbox.get("x0")
        meta["bbox_y0"] = bbox.get("y0")
        meta["bbox_x1"] = bbox.get("x1")
        meta["bbox_y1"] = bbox.get("y1")
    return meta


def _embedding_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in values) + "]"


class SupabaseIndex:
    name = "supabase"

    def __init__(self) -> None:
        self._db = _client()
        self._embeddings = tracked_embeddings()
        self._table = SUPABASE_CHUNKS_TABLE

    def upsert(self, documents: list[Document], *, reset: bool = True) -> int:
        if reset:
            self._db.table(self._table).delete().gte("chunk_index", 0).execute()
        vectors = self._embeddings.embed_documents([d.page_content for d in documents])
        rows = []
        for doc, vector in zip(documents, vectors, strict=True):
            meta = dict(doc.metadata)
            rows.append(
                {
                    "content": doc.page_content,
                    "embedding": _embedding_literal(list(vector)),
                    "source_file": meta.get("source_file") or meta.get("source"),
                    "doc_type": meta.get("doc_type") or "unknown",
                    "chunk_index": int(meta.get("chunk_index") or 0),
                    "page": meta.get("page"),
                    "page_width": meta.get("page_width"),
                    "page_height": meta.get("page_height"),
                    "bbox": _bbox_json(meta),
                    "polygon": _jsonish(meta.get("polygon")),
                    "polygon_norm": _jsonish(meta.get("polygon_norm")),
                    "extraction": meta.get("extraction"),
                }
            )
        batch = 80
        for i in range(0, len(rows), batch):
            self._db.table(self._table).insert(rows[i : i + batch]).execute()
        return self.count()

    def similarity_search(self, query: str, k: int) -> list[Hit]:
        vector = self._embeddings.embed_query(query)
        resp = self._db.rpc(
            "match_chunks",
            {"query_embedding": _embedding_literal(list(vector)), "match_count": k},
        ).execute()
        return [(row["content"], _row_to_meta(row)) for row in (resp.data or [])]

    def lexical_search(self, query: str, k: int) -> list[Hit]:
        resp = self._db.rpc(
            "search_chunks_fts",
            {"query_text": query, "match_count": k},
        ).execute()
        return [(row["content"], _row_to_meta(row)) for row in (resp.data or [])]

    def count(self) -> int:
        resp = self._db.table(self._table).select("id", count="exact").limit(1).execute()
        return int(resp.count or 0)
