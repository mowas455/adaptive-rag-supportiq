"""Langfuse v2 callback handler + custom scores for SupportIQ traces."""

from __future__ import annotations

import logging
from typing import Any

from src.config import (
    LANGFUSE_ENABLED,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)

logger = logging.getLogger(__name__)


def _ensure_langchain_shims() -> None:
    from src.observability.langchain_compat import install_langchain_v1_shims

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


def auth_ok() -> bool:
    if not LANGFUSE_ENABLED:
        return False
    try:
        return bool(get_langfuse().auth_check())
    except Exception:
        return False
