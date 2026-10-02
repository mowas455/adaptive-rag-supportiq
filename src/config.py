"""Shared paths and environment for SupportIQ."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def env_path(name: str, default: str) -> Path:
    raw = os.getenv(name, default)
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.2")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
CHROMA_PERSIST_DIR = env_path("CHROMA_PERSIST_DIR", "chroma_db")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "supportiq")
ORDERS_DB = env_path("ORDERS_DB", "data/orders.db")
WEB_SEARCH_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "duckduckgo").lower()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "lf_pk_supportiq_local")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "lf_sk_supportiq_local")
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "true").lower() in {"1", "true", "yes"}

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))

RETRIEVE_K = 4
MAX_REWRITE_RETRIES = 1
MAX_REGENERATE_RETRIES = 1
ROUTER_MIN_CONFIDENCE = float(os.getenv("ROUTER_MIN_CONFIDENCE", "0.55"))
ROUTER_MODEL_PATH = env_path("ROUTER_MODEL_PATH", "models/router.joblib")

INSUFFICIENT_INFO_MESSAGE = (
    "I don't have enough information to answer that reliably from the available sources. "
    "Please rephrase the question or provide an order number / more detail."
)
