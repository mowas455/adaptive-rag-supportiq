"""LangGraph nodes: classify, retrieve, grade, rewrite, sql, web, generate, grade answer."""

from __future__ import annotations

from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_ollama import OllamaEmbeddings

from src.config import (
    CHROMA_COLLECTION,
    CHROMA_PERSIST_DIR,
    INSUFFICIENT_INFO_MESSAGE,
    MAX_REGENERATE_RETRIES,
    MAX_REWRITE_RETRIES,
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    RETRIEVE_K,
)
from src.graph.llm import get_llm, structured_invoke
from src.graph.schemas import (
    AnswerGrade,
    DocumentGrades,
    OrderLookupParse,
    RewrittenQuery,
    RouteDecision,
)
from src.graph.state import GraphState, RetrievedDoc
from src.retrieval.hybrid import hybrid_search
from src.router.embed_router import route_question
from src.tools.sql_tool import extract_email, extract_order_id, format_orders, lookup_orders
from src.tools.web_search_tool import format_results, search_web

CLASSIFY_SYSTEM = """You are the query router for NexCart SupportIQ, a customer-support assistant.

Choose exactly one source:
- vectorstore: policies, FAQs, shipping, returns, billing, product manuals, troubleshooting,
  how-to questions about NexCart products or account rules. Always use vectorstore for
  PulseBuds, HomePlug, LockStep, GlowBar, NexCart Plus, returns, shipping, and billing.
  Example: "What's your return window?" / "PulseBuds will not pair."
- sql_lookup: a specific customer order — status, ETA, items, tracking-like questions that
  mention an order number (e.g. 4521) or a customer email. Example: "Where is order #4521?"
- web_search: live/current events, outages, weather, news, competitors, or anything that
  cannot be in the internal knowledge base or orders table. Example: "Is there an outage right now?"

If the question mixes an order ID with a policy question, prefer sql_lookup when they want
that order's status; otherwise vectorstore.
"""

GRADE_DOCS_SYSTEM = """You grade retrieved documents for a support RAG system.
Mark a document relevant only if it contains facts that help answer the question.
Mark it irrelevant if it is off-topic or too generic to help."""

REWRITE_SYSTEM = """The retrieved documents did not answer the question.
Rewrite the query to be more specific for search (synonyms, product names, policy terms).
Return only an improved query, not an answer."""

GENERATE_SYSTEM = """You are SupportIQ, a helpful NexCart customer-support assistant.
Answer using ONLY the provided context. Copy key figures (days, fees, statuses, ETAs) exactly.
If asked where an order is, report status, ETA, email, and items from the record.
Do not invent ship dates, tracking numbers, GPS locations, or a placeholder like [date].
Do not add "contact support" boilerplate unless it is in the context.
If the context is missing a fact, say you don't know. Be concise (2–6 sentences)."""

ANSWER_GRADE_SYSTEM = """You grade a support assistant's answer against retrieved context.

grounded=true if the answer's facts are present in the context, including reasonable paraphrase.
grounded=false ONLY if the answer invents numbers, dates, fees, product names, statuses, or policies
that do not appear in the context.
relevant=true if the answer addresses the user's question (partial answers still count).
A short refusal that admits missing info is grounded=true and relevant=false."""


@lru_cache(maxsize=1)
def _vectorstore() -> Chroma:
    embeddings = OllamaEmbeddings(model=OLLAMA_EMBED_MODEL, base_url=OLLAMA_BASE_URL)
    return Chroma(
        persist_directory=str(CHROMA_PERSIST_DIR),
        collection_name=CHROMA_COLLECTION,
        embedding_function=embeddings,
    )


def reset_vectorstore_cache() -> None:
    _vectorstore.cache_clear()


def _docs_to_context(docs: list[RetrievedDoc]) -> str:
    if not docs:
        return "(no context)"
    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(
            f"[doc {i} | {doc.get('source', 'unknown')} | {doc.get('doc_type', '')}]\n{doc['content']}"
        )
    return "\n\n".join(parts)


def classify_query(state: GraphState, config: RunnableConfig | None = None) -> dict:
    question = state["question"]
    route, backend, rationale, confidence = route_question(question)
    if backend == "needs_llm":
        decision = structured_invoke(
            RouteDecision,
            [
                SystemMessage(content=CLASSIFY_SYSTEM),
                HumanMessage(content=f"User question:\n{question}"),
            ],
            config=config,
        )
        route = decision.source
        rationale = f"{rationale}; LLM: {decision.rationale}"
        backend = "llm"
    return {
        "route": route,
        "source_type": route,
        "search_query": question,
        "routing_rationale": rationale,
        "router_backend": backend,
        "retry_count": state.get("retry_count", 0),
        "regenerate_count": state.get("regenerate_count", 0),
        "documents": [],
        "retrieved_docs": [],
        "needs_regeneration": False,
        "extra": {"router_confidence": confidence},
    }


def retrieve(state: GraphState, config: RunnableConfig | None = None) -> dict:
    query = state.get("search_query") or state["question"]
    documents = hybrid_search(_vectorstore(), query, k=RETRIEVE_K)
    return {
        "documents": documents,
        "retrieved_docs": documents,
        "source_type": "vectorstore",
    }


def grade_documents(state: GraphState, config: RunnableConfig | None = None) -> dict:
    question = state["question"]
    documents = list(state.get("documents") or [])
    if not documents:
        return {"documents": [], "retrieved_docs": [], "docs_relevant_count": 0}

    numbered = "\n\n".join(
        f"--- document {i} ---\n{d['content'][:2000]}" for i, d in enumerate(documents)
    )
    grades = structured_invoke(
        DocumentGrades,
        [
            SystemMessage(content=GRADE_DOCS_SYSTEM),
            HumanMessage(content=f"Question:\n{question}\n\nDocuments:\n{numbered}"),
        ],
        config=config,
    )
    relevant_idx = {g.index for g in grades.grades if g.relevant}
    filtered = [doc for i, doc in enumerate(documents) if i in relevant_idx]
    return {
        "documents": filtered,
        "retrieved_docs": filtered,
        "docs_relevant_count": len(filtered),
    }


def rewrite_query(state: GraphState, config: RunnableConfig | None = None) -> dict:
    rewritten = structured_invoke(
        RewrittenQuery,
        [
            SystemMessage(content=REWRITE_SYSTEM),
            HumanMessage(content=f"Original question:\n{state['question']}"),
        ],
        config=config,
    )
    retry_count = int(state.get("retry_count") or 0) + 1
    return {
        "search_query": rewritten.query,
        "retry_count": retry_count,
    }


def sql_lookup(state: GraphState, config: RunnableConfig | None = None) -> dict:
    question = state["question"]
    order_id = extract_order_id(question)
    email = extract_email(question)
    if not order_id and not email:
        parsed = structured_invoke(
            OrderLookupParse,
            [
                SystemMessage(
                    content="Extract order_id (digits) and/or customer_email from the question. "
                    "Use null if not present."
                ),
                HumanMessage(content=question),
            ],
            config=config,
        )
        order_id = parsed.order_id or None
        email = parsed.customer_email or None

    rows = lookup_orders(order_id=order_id, customer_email=email)
    content = format_orders(rows)
    if order_id or email:
        content += f"\n\nLookup keys: order_id={order_id!r}, email={email!r}"
    documents: list[RetrievedDoc] = [
        {"content": content, "source": "orders.db", "chunk_index": 0, "doc_type": "orders"}
    ]
    return {
        "documents": documents,
        "retrieved_docs": documents,
        "source_type": "sql_lookup",
        "docs_relevant_count": 1 if rows else 0,
    }


def web_search(state: GraphState, config: RunnableConfig | None = None) -> dict:
    query = state.get("search_query") or state["question"]
    results = search_web(query)
    content = format_results(results)
    documents: list[RetrievedDoc] = [
        {
            "content": f"{item.get('title', '')}\n{item.get('url', '')}\n{item.get('snippet', '')}",
            "source": item.get("url") or "web_search",
            "chunk_index": i,
            "doc_type": "web",
        }
        for i, item in enumerate(results)
    ]
    if not documents:
        documents = [{"content": content, "source": "web_search", "chunk_index": 0, "doc_type": "web"}]
    return {
        "documents": documents,
        "retrieved_docs": documents,
        "source_type": "web_search",
        "docs_relevant_count": len(results),
        "retry_count": max(int(state.get("retry_count") or 0), 1)
        if state.get("route") == "vectorstore"
        else int(state.get("retry_count") or 0),
    }


def generate(state: GraphState, config: RunnableConfig | None = None) -> dict:
    question = state["question"]
    context = _docs_to_context(list(state.get("documents") or []))
    prior = (state.get("answer") or "").strip()
    extra = ""
    if state.get("needs_regeneration") and prior:
        extra = (
            "\n\nYour previous draft was flagged as insufficiently grounded. "
            f"Rewrite it so every fact is taken from the context.\nPrevious draft:\n{prior}"
        )
    llm = get_llm(temperature=0.0)
    message = llm.invoke(
        [
            SystemMessage(content=GENERATE_SYSTEM),
            HumanMessage(
                content=f"Question:\n{question}\n\nContext:\n{context}{extra}\n\nAnswer:"
            ),
        ],
        config=config,
    )
    answer = message.content if isinstance(message.content, str) else str(message.content)
    return {"answer": answer.strip(), "needs_regeneration": False}


def grade_answer(state: GraphState, config: RunnableConfig | None = None) -> dict:
    question = state["question"]
    answer = state.get("answer") or ""
    context = _docs_to_context(list(state.get("documents") or []))
    grade = structured_invoke(
        AnswerGrade,
        [
            SystemMessage(content=ANSWER_GRADE_SYSTEM),
            HumanMessage(
                content=(
                    f"Question:\n{question}\n\nContext:\n{context}\n\nAnswer:\n{answer}"
                )
            ),
        ],
        config=config,
    )
    regenerate_count = int(state.get("regenerate_count") or 0)
    # Spec: retry/abstain is driven by groundedness. Relevance is recorded but does
    # not discard a grounded answer (llama3.2 often confuses the two flags).
    if grade.grounded:
        return {
            "grounded": True,
            "answer_relevant": grade.relevant,
            "groundedness_score": 1.0,
            "needs_regeneration": False,
        }

    if regenerate_count < MAX_REGENERATE_RETRIES:
        return {
            "grounded": False,
            "answer_relevant": grade.relevant,
            "groundedness_score": 0.0,
            "regenerate_count": regenerate_count + 1,
            "needs_regeneration": True,
        }

    return {
        "answer": INSUFFICIENT_INFO_MESSAGE,
        "grounded": False,
        "answer_relevant": False,
        "groundedness_score": 0.0,
        "needs_regeneration": False,
    }


def route_after_classify(state: GraphState) -> str:
    return state.get("route") or "web_search"


def route_after_grade_docs(state: GraphState) -> str:
    relevant = int(state.get("docs_relevant_count") or 0)
    retries = int(state.get("retry_count") or 0)
    if relevant > 0:
        return "generate"
    if retries < MAX_REWRITE_RETRIES:
        return "rewrite_query"
    return "web_search"


def route_after_grade_answer(state: GraphState) -> str:
    if state.get("needs_regeneration"):
        return "generate"
    return "end"
