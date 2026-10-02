"""FastAPI surface for SupportIQ: ingest, chat, health."""

from __future__ import annotations

from typing import Any

import httpx
from ai.config import (
    CHROMA_COLLECTION,
    CHROMA_PERSIST_DIR,
    LANGFUSE_HOST,
    OLLAMA_BASE_URL,
    ORDERS_DB,
)
from ai.graph.build_graph import run_supportiq
from ai.graph.nodes import _vectorstore, reset_vectorstore_cache
from ai.ingestion.embed_and_store import ingest
from ai.ingestion.pdf_preview import render_page_preview
from ai.observability.langfuse_client import auth_ok, fetch_trace
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

app = FastAPI(title="SupportIQ Adaptive RAG", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: str = Field(default="default")


class Point(BaseModel):
    x: float
    y: float


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class Citation(BaseModel):
    id: int
    source: str | None = None
    doc_type: str | None = None
    chunk_index: int | None = None
    snippet: str = ""
    page: int | None = None
    page_width: float | None = None
    page_height: float | None = None
    bbox: BBox | None = None
    polygon: list[Point] = Field(default_factory=list)
    polygon_norm: list[Point] = Field(default_factory=list)
    extraction: str | None = None


class ChatResponse(BaseModel):
    answer: str
    source_type: str
    retries: int
    trace_url: str | None = None
    route: str | None = None
    regenerate_count: int = 0
    groundedness_score: float | None = None
    citations: list[Citation] = Field(default_factory=list)
    router_backend: str | None = None
    routing_rationale: str | None = None
    search_query: str | None = None
    docs_relevant_count: int = 0
    trace_id: str | None = None
    usage: dict[str, Any] | None = None


class IngestResponse(BaseModel):
    chunk_count: int
    collection_size: int
    order_count: int
    source_files: list[str]


class HealthResponse(BaseModel):
    status: str
    ollama: bool
    chroma: bool
    langfuse: bool
    details: dict[str, Any]


@app.post("/ingest", response_model=IngestResponse)
def post_ingest() -> IngestResponse:
    try:
        summary = ingest(reset_chroma=True)
        reset_vectorstore_cache()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return IngestResponse(
        chunk_count=summary["chunk_count"],
        collection_size=summary["collection_size"],
        order_count=summary["order_count"],
        source_files=list(summary["source_files"]),
    )


@app.post("/chat", response_model=ChatResponse)
def post_chat(body: ChatRequest) -> ChatResponse:
    try:
        result = run_supportiq(body.question, session_id=body.session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(
        answer=result["answer"],
        source_type=result["source_type"],
        retries=int(result["retry_count"]),
        trace_url=result.get("trace_url"),
        route=result.get("route"),
        regenerate_count=int(result.get("regenerate_count") or 0),
        groundedness_score=result.get("groundedness_score"),
        citations=result.get("citations") or [],
        router_backend=result.get("router_backend"),
        routing_rationale=result.get("routing_rationale"),
        search_query=result.get("search_query"),
        docs_relevant_count=int(result.get("docs_relevant_count") or 0),
        trace_id=result.get("trace_id"),
        usage=result.get("usage"),
    )


@app.get("/pdf-preview")
def get_pdf_preview(
    source: str = Query(..., min_length=1),
    page: int = Query(..., ge=1),
    x0: float | None = None,
    y0: float | None = None,
    x1: float | None = None,
    y1: float | None = None,
) -> Response:
    try:
        png = render_page_preview(source, page, x0=x0, y0=y0, x1=x1, y1=y1)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(content=png, media_type="image/png")


@app.get("/traces/{trace_id}")
def get_trace(trace_id: str) -> dict[str, Any]:
    try:
        return fetch_trace(trace_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    details: dict[str, Any] = {}
    ollama_ok = False
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=3.0)
        ollama_ok = resp.status_code == 200
        details["ollama"] = "ok" if ollama_ok else f"status {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        details["ollama"] = str(exc)

    chroma_ok = False
    try:
        count = _vectorstore()._collection.count()  # noqa: SLF001
        chroma_ok = count > 0
        details["chroma"] = {
            "persist_dir": str(CHROMA_PERSIST_DIR),
            "collection": CHROMA_COLLECTION,
            "count": count,
        }
    except Exception as exc:  # noqa: BLE001
        details["chroma"] = str(exc)

    langfuse_ok = False
    try:
        langfuse_ok = auth_ok()
        details["langfuse"] = {"host": LANGFUSE_HOST, "ok": langfuse_ok}
    except Exception as exc:  # noqa: BLE001
        details["langfuse"] = str(exc)

    details["orders_db"] = str(ORDERS_DB)
    status = "ok" if (ollama_ok and chroma_ok) else "degraded"
    return HealthResponse(
        status=status,
        ollama=ollama_ok,
        chroma=chroma_ok,
        langfuse=langfuse_ok,
        details=details,
    )
