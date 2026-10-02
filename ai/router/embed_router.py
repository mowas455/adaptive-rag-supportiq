"""Embedding 3-way router with heuristic + sklearn, LLM fallback."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

import numpy as np

from ai.config import ROUTER_MIN_CONFIDENCE, ROUTER_MODEL_PATH
from ai.observability.usage import tracked_embeddings
from ai.tools.sql_tool import extract_email, extract_order_id

RouteName = Literal["vectorstore", "sql_lookup", "web_search"]
LIVE_HINTS = (
    "right now",
    "today",
    "this week",
    "outage",
    "weather",
    "stock market",
    "breaking",
    "current weather",
    "current events",
    "live",
)


@lru_cache(maxsize=1)
def _embeddings():
    return tracked_embeddings()


@lru_cache(maxsize=1)
def _sklearn_bundle() -> tuple | None:
    path = ROUTER_MODEL_PATH
    if not path.exists():
        return None
    import joblib

    return joblib.load(path)


def heuristic_route(question: str) -> tuple[RouteName, str] | None:
    if extract_order_id(question) or extract_email(question):
        return "sql_lookup", "heuristic: order id or email in the question"
    q = question.lower()
    if any(h in q for h in LIVE_HINTS) and not any(
        w in q for w in ("nexcart", "return", "pulsebuds", "plus", "glowbar", "homeplug")
    ):
        return "web_search", "heuristic: live/current-events phrasing"
    return None


def sklearn_route(question: str) -> tuple[RouteName, float, str] | None:
    bundle = _sklearn_bundle()
    if bundle is None:
        return None
    clf, labels = bundle
    vec = np.array(_embeddings().embed_query(question)).reshape(1, -1)
    proba = clf.predict_proba(vec)[0]
    idx = int(np.argmax(proba))
    conf = float(proba[idx])
    label = str(labels[idx])
    return label, conf, f"sklearn LogisticRegression p={conf:.2f}"


def route_question(question: str) -> tuple[RouteName, str, str, float | None]:
    """
    Returns (route, backend, rationale, confidence).
    backend is heuristic | sklearn | needs_llm.
    """
    hit = heuristic_route(question)
    if hit:
        return hit[0], "heuristic", hit[1], 1.0
    sk = sklearn_route(question)
    if sk and sk[1] >= ROUTER_MIN_CONFIDENCE:
        return sk[0], "sklearn", sk[2], sk[1]
    if sk:
        return sk[0], "needs_llm", f"sklearn uncertain ({sk[2]}); defer to LLM", sk[1]
    return "vectorstore", "needs_llm", "no router model on disk; defer to LLM", None
