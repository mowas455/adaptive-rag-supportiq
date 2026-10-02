"""Thin Streamlit chat UI for SupportIQ."""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlencode

import httpx
import streamlit as st

API_URL = os.getenv("SUPPORTIQ_API_URL", "http://127.0.0.1:8000").rstrip("/")

ROUTE_COLORS = {
    "vectorstore": "blue",
    "sql_lookup": "green",
    "web_search": "orange",
}


def _post_chat(question: str, session_id: str) -> dict:
    with httpx.Client(timeout=180.0) as client:
        resp = client.post(
            f"{API_URL}/chat",
            json={"question": question, "session_id": session_id},
        )
        resp.raise_for_status()
        return resp.json()


def _health() -> dict | None:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{API_URL}/health")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


def _citation_block(c: dict) -> None:
    source = c.get("source") or "unknown"
    page = c.get("page")
    bbox = c.get("bbox") or {}
    if page and str(source).endswith(".pdf"):
        params = {"source": source, "page": int(page)}
        if bbox:
            params.update(
                {
                    "x0": bbox.get("x0"),
                    "y0": bbox.get("y0"),
                    "x1": bbox.get("x1"),
                    "y1": bbox.get("y1"),
                }
            )
        st.image(
            f"{API_URL}/pdf-preview?{urlencode(params)}",
            caption=f"{source}  ·  page {page}",
            width=520,
        )
    elif c.get("snippet"):
        st.caption(source)
        st.write(c.get("snippet") or "")


st.set_page_config(page_title="SupportIQ", page_icon="🧭", layout="wide")
st.title("SupportIQ")
st.caption("Adaptive RAG customer support — vectorstore / SQL / web, with self-correction.")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

health = _health()
left, right = st.columns([2, 1])
with right:
    st.subheader("Status")
    if health is None:
        st.error(f"API not reachable at {API_URL}. Start FastAPI first.")
    else:
        st.write(f"API: `{health.get('status')}`")
        st.write(f"Ollama: {'ok' if health.get('ollama') else 'down'}")
        st.write(f"Chroma: {'ok' if health.get('chroma') else 'down'}")
        st.write(f"Langfuse: {'ok' if health.get('langfuse') else 'down'}")
    st.caption(f"session `{st.session_state.session_id}`")

with left:
    for item in st.session_state.messages:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            if item["role"] == "assistant":
                route = item.get("source_type") or "unknown"
                retries = int(item.get("retries") or 0)
                st.badge(route, color=ROUTE_COLORS.get(route, "gray"))
                if retries:
                    st.badge("retry", color="red")
                if item.get("trace_url"):
                    st.markdown(f"[Open Langfuse trace]({item['trace_url']})")
                cites = item.get("citations") or []
                if cites:
                    with st.expander(f"Citations ({len(cites)})"):
                        for c in cites:
                            _citation_block(c)

    prompt = st.chat_input("Ask about returns, an order ID, or a live outage…")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Routing and generating…"):
                try:
                    data = _post_chat(prompt, st.session_state.session_id)
                except Exception as exc:
                    st.error(str(exc))
                    st.stop()
            st.markdown(data.get("answer", ""))
            route = data.get("source_type") or "unknown"
            retries = int(data.get("retries") or 0)
            try:
                st.badge(route, color=ROUTE_COLORS.get(route, "gray"))
                if retries:
                    st.badge("retry", color="red")
            except Exception:
                st.caption(f"route: {route} · retries: {retries}")
            if data.get("trace_url"):
                st.markdown(f"[Open Langfuse trace]({data['trace_url']})")
            cites = data.get("citations") or []
            if cites:
                with st.expander(f"Citations ({len(cites)})"):
                    for c in cites:
                        _citation_block(c)
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": data.get("answer", ""),
                "source_type": route,
                "retries": retries,
                "trace_url": data.get("trace_url"),
                "citations": data.get("citations") or [],
            }
        )
