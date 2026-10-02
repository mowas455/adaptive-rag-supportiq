"""Langfuse v2 callback handler + custom scores for SupportIQ traces."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ai.config import (
    LANGFUSE_ENABLED,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)

logger = logging.getLogger(__name__)


def _ensure_langchain_shims() -> None:
    from ai.observability.langchain_compat import install_langchain_v1_shims

    install_langchain_v1_shims()


def get_langfuse():
    from langfuse import Langfuse

    return Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
        enabled=LANGFUSE_ENABLED,
    )


def make_callback_handler(
    *,
    session_id: str | None = None,
    trace_name: str = "supportiq-chat",
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
):
    """One handler per request so concurrent FastAPI calls don't share a trace."""
    if not LANGFUSE_ENABLED:
        return None
    _ensure_langchain_shims()
    from langfuse.callback import CallbackHandler

    return CallbackHandler(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
        session_id=session_id,
        trace_name=trace_name,
        metadata=metadata or {},
        tags=tags or ["supportiq"],
        enabled=True,
    )


def log_run_scores(
    handler,
    *,
    route: str,
    docs_relevant_count: int,
    retry_count: int,
    regenerate_count: int,
    groundedness_score: float | None,
    citation_count: int = 0,
    usage: dict[str, Any] | None = None,
) -> None:
    if handler is None or getattr(handler, "trace", None) is None:
        return
    try:
        client = handler.langfuse or get_langfuse()
        trace_id = handler.trace.id
        client.score(
            name="routing_decision",
            value=route,
            data_type="CATEGORICAL",
            trace_id=trace_id,
        )
        client.score(
            name="docs_relevant_count",
            value=float(docs_relevant_count),
            data_type="NUMERIC",
            trace_id=trace_id,
        )
        retried = bool(retry_count or regenerate_count)
        client.score(
            name="retry_triggered",
            value=1.0 if retried else 0.0,
            data_type="BOOLEAN",
            trace_id=trace_id,
        )
        client.score(
            name="groundedness_score",
            value=float(groundedness_score or 0.0),
            data_type="NUMERIC",
            trace_id=trace_id,
        )
        client.score(
            name="citation_count",
            value=float(citation_count),
            data_type="NUMERIC",
            trace_id=trace_id,
        )
        llm = (usage or {}).get("llm") or {}
        emb = (usage or {}).get("embedding") or {}
        client.score(
            name="llama_prompt_tokens",
            value=float(llm.get("prompt_tokens") or 0),
            data_type="NUMERIC",
            trace_id=trace_id,
        )
        client.score(
            name="llama_completion_tokens",
            value=float(llm.get("completion_tokens") or 0),
            data_type="NUMERIC",
            trace_id=trace_id,
        )
        client.score(
            name="nomic_embed_tokens",
            value=float(emb.get("prompt_tokens") or 0),
            data_type="NUMERIC",
            trace_id=trace_id,
        )
    except Exception:
        logger.exception("Failed to write Langfuse scores")


def flush_and_trace_url(handler) -> tuple[str | None, str | None]:
    if handler is None:
        return None, None
    try:
        handler.flush()
        trace_id = handler.get_trace_id()
        url = handler.get_trace_url()
        return trace_id, url
    except Exception:
        logger.exception("Failed to flush Langfuse handler")
        return None, None


def fetch_trace(trace_id: str) -> dict[str, Any]:
    """Load a trace via Langfuse's public API (the web UI cannot be iframed)."""
    import base64

    if not LANGFUSE_ENABLED:
        raise RuntimeError("Langfuse is disabled")
    token = base64.b64encode(
        f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()
    ).decode()
    url = f"{LANGFUSE_HOST.rstrip('/')}/api/public/traces/{trace_id}"
    with httpx.Client(timeout=8.0) as client:
        resp = client.get(url, headers={"Authorization": f"Basic {token}"})
    if resp.status_code == 404:
        raise FileNotFoundError(trace_id)
    resp.raise_for_status()
    payload = resp.json()
    observations = payload.get("observations") or []
    scores = payload.get("scores") or []
    steps = []
    for obs in observations:
        steps.append(
            {
                "id": obs.get("id"),
                "name": obs.get("name") or obs.get("type"),
                "type": obs.get("type"),
                "start_time": obs.get("startTime"),
                "end_time": obs.get("endTime"),
                "model": obs.get("model"),
                "level": obs.get("level"),
                "prompt_tokens": (obs.get("usage") or {}).get("input")
                or (obs.get("usage") or {}).get("promptTokens"),
                "completion_tokens": (obs.get("usage") or {}).get("output")
                or (obs.get("usage") or {}).get("completionTokens"),
            }
        )
    steps.sort(key=lambda row: row.get("start_time") or "")
    llm_prompt = sum(int(s.get("prompt_tokens") or 0) for s in steps)
    llm_completion = sum(int(s.get("completion_tokens") or 0) for s in steps)
    return {
        "id": payload.get("id") or trace_id,
        "name": payload.get("name"),
        "session_id": payload.get("sessionId"),
        "timestamp": payload.get("timestamp"),
        "html_path": f"{LANGFUSE_HOST.rstrip('/')}/trace/{trace_id}",
        "scores": [
            {
                "name": s.get("name"),
                "value": s.get("value"),
                "data_type": s.get("dataType") or s.get("data_type"),
            }
            for s in scores
        ],
        "observations": steps,
        "token_totals": {
            "llm_prompt_tokens": llm_prompt,
            "llm_completion_tokens": llm_completion,
        },
    }


def auth_ok() -> bool:
    if not LANGFUSE_ENABLED:
        return False
    try:
        return bool(get_langfuse().auth_check())
    except Exception:
        return False
