"""LangGraph state schema for the SupportIQ adaptive RAG flow."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

RouteName = Literal["vectorstore", "sql_lookup", "web_search"]


class BBox(TypedDict):
    x0: float
    y0: float
    x1: float
    y1: float


class Point(TypedDict):
    x: float
    y: float


class RetrievedDoc(TypedDict, total=False):
    content: str
    source: str
    chunk_index: int
    doc_type: str
    page: int
    page_width: float
    page_height: float
    bbox: BBox
    polygon: list[Point]
    polygon_norm: list[Point]
    extraction: str


class GraphState(TypedDict, total=False):
    question: str
    search_query: str
    route: RouteName
    source_type: str
    documents: list[RetrievedDoc]
    retrieved_docs: list[RetrievedDoc]
    answer: str
    retry_count: int
    regenerate_count: int
    docs_relevant_count: int
    grounded: bool
    answer_relevant: bool
    groundedness_score: float
    needs_regeneration: bool
    routing_rationale: str
    router_backend: str
    extra: dict[str, Any]
