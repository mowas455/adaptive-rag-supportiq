"""LangGraph state schema for the SupportIQ adaptive RAG flow."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

RouteName = Literal["vectorstore", "sql_lookup", "web_search"]


class RetrievedDoc(TypedDict):
    content: str
    source: str


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
    extra: dict[str, Any]
