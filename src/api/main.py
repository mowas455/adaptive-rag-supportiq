"""FastAPI surface for SupportIQ: ingest, chat, health."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import (
    CHROMA_COLLECTION,
    CHROMA_PERSIST_DIR,
    LANGFUSE_HOST,
    OLLAMA_BASE_URL,
    ORDERS_DB,
)
from src.graph.build_graph import run_supportiq
from src.graph.nodes import _vectorstore, reset_vectorstore_cache
from src.ingestion.embed_and_store import ingest
from src.observability.langfuse_client import auth_ok

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


class Citation(BaseModel):
    id: int
    source: str | None = None
    doc_type: str | None = None
    chunk_index: int | None = None
    snippet: str = ""


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
    )


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
