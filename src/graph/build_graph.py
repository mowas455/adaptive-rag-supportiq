"""Wire SupportIQ nodes into a LangGraph StateGraph with conditional edges."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from langgraph.graph import END, START, StateGraph

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.nodes import (  # noqa: E402
    classify_query,
    generate,
    grade_answer,
    grade_documents,
    retrieve,
    rewrite_query,
    route_after_classify,
    route_after_grade_answer,
    route_after_grade_docs,
    sql_lookup,
    web_search,
)
from src.graph.state import GraphState  # noqa: E402

_COMPILED = None


def build_graph():
    """
    Adaptive RAG control flow:

        classify_query
           ├─ vectorstore → retrieve → grade_documents
           │                    ├─ relevant docs → generate → grade_answer
           │                    ├─ none + retry_count==0 → rewrite_query → retrieve (once)
           │                    └─ none + already retried → web_search → generate
           ├─ sql_lookup → generate → grade_answer
           └─ web_search → generate → grade_answer

        grade_answer
           ├─ grounded+relevant → END
           ├─ fail + regenerate_count==0 → generate (once)
           └─ fail again → abstain message → END
    """
    graph = StateGraph(GraphState)

    graph.add_node("classify_query", classify_query)
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade_documents", grade_documents)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("sql_lookup", sql_lookup)
    graph.add_node("web_search", web_search)
    graph.add_node("generate", generate)
    graph.add_node("grade_answer", grade_answer)

    graph.add_edge(START, "classify_query")
    graph.add_conditional_edges(
        "classify_query",
        route_after_classify,
        {
            "vectorstore": "retrieve",
            "sql_lookup": "sql_lookup",
            "web_search": "web_search",
        },
    )
    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges(
        "grade_documents",
        route_after_grade_docs,
        {
            "generate": "generate",
            "rewrite_query": "rewrite_query",
            "web_search": "web_search",
        },
    )
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("sql_lookup", "generate")
    graph.add_edge("web_search", "generate")
    graph.add_edge("generate", "grade_answer")
    graph.add_conditional_edges(
        "grade_answer",
        route_after_grade_answer,
        {
            "generate": "generate",
            "end": END,
        },
    )
    return graph.compile()


def get_graph():
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_graph()
    return _COMPILED


def run_supportiq(
    question: str,
    *,
    session_id: str | None = None,
    trace_name: str = "supportiq-chat",
) -> dict:
    from src.observability.langfuse_client import (
        flush_and_trace_url,
        log_run_scores,
        make_callback_handler,
    )

    handler = None
    try:
        handler = make_callback_handler(
            session_id=session_id,
            trace_name=trace_name,
            metadata={"question": question},
        )
    except Exception:
        handler = None
    callbacks = [handler] if handler is not None else []
    result = get_graph().invoke(
        {
            "question": question,
            "retry_count": 0,
            "regenerate_count": 0,
            "documents": [],
            "retrieved_docs": [],
        },
        {"recursion_limit": 20, "callbacks": callbacks, "run_name": trace_name},
    )
    route = result.get("route") or result.get("source_type") or ""
    retry_count = int(result.get("retry_count") or 0)
    regenerate_count = int(result.get("regenerate_count") or 0)
    docs_relevant_count = int(result.get("docs_relevant_count") or 0)
    groundedness_score = result.get("groundedness_score")
    log_run_scores(
        handler,
        route=str(route),
        docs_relevant_count=docs_relevant_count,
        retry_count=retry_count,
        regenerate_count=regenerate_count,
        groundedness_score=groundedness_score,
        citation_count=len(result.get("retrieved_docs") or []),
    )
    trace_id, trace_url = flush_and_trace_url(handler)
    citations = []
    for i, doc in enumerate(result.get("retrieved_docs") or [], 1):
        snippet = " ".join((doc.get("content") or "").split())
        if len(snippet) > 220:
            snippet = snippet[:217] + "..."
        citations.append(
            {
                "id": i,
                "source": doc.get("source"),
                "doc_type": doc.get("doc_type"),
                "chunk_index": doc.get("chunk_index"),
                "snippet": snippet,
            }
        )
    return {
        "answer": result.get("answer", ""),
        "source_type": result.get("source_type", ""),
        "route": route,
        "retrieved_docs": result.get("retrieved_docs", []),
        "citations": citations,
        "retry_count": retry_count,
        "regenerate_count": regenerate_count,
        "docs_relevant_count": docs_relevant_count,
        "groundedness_score": groundedness_score,
        "routing_rationale": result.get("routing_rationale"),
        "router_backend": result.get("router_backend"),
        "search_query": result.get("search_query"),
        "trace_id": trace_id,
        "trace_url": trace_url,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one SupportIQ Adaptive RAG question")
    parser.add_argument("question", nargs="?", help="User question")
    parser.add_argument("--mermaid", action="store_true", help="Print graph mermaid and exit")
    args = parser.parse_args()

    graph = get_graph()
    if args.mermaid:
        print(graph.get_graph().draw_mermaid())
        return
    if not args.question:
        parser.error("question is required unless --mermaid is set")

    result = run_supportiq(args.question)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
