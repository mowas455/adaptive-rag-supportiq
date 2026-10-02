"""Per-request token accounting for llama3.2 and nomic-embed-text."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_ollama import OllamaEmbeddings

from ai.config import OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL, OLLAMA_LLM_MODEL


@dataclass
class UsageTotals:
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    llm_calls: int = 0
    embed_prompt_tokens: int = 0
    embed_calls: int = 0
    seen_ids: set[str] = field(default_factory=set)

    def as_dict(self) -> dict[str, Any]:
        return {
            "llm": {
                "model": OLLAMA_LLM_MODEL,
                "prompt_tokens": self.llm_prompt_tokens,
                "completion_tokens": self.llm_completion_tokens,
                "total_tokens": self.llm_prompt_tokens + self.llm_completion_tokens,
                "calls": self.llm_calls,
            },
            "embedding": {
                "model": OLLAMA_EMBED_MODEL,
                "prompt_tokens": self.embed_prompt_tokens,
                "calls": self.embed_calls,
            },
        }


_current: ContextVar[UsageTotals | None] = ContextVar("supportiq_usage", default=None)


def begin_usage() -> UsageTotals:
    totals = UsageTotals()
    _current.set(totals)
    return totals


def current_usage() -> UsageTotals | None:
    return _current.get()


def snapshot_usage() -> dict[str, Any]:
    totals = _current.get()
    return totals.as_dict() if totals else UsageTotals().as_dict()


def record_llm(*, prompt_tokens: int, completion_tokens: int) -> None:
    totals = _current.get()
    if totals is None:
        return
    totals.llm_prompt_tokens += max(int(prompt_tokens), 0)
    totals.llm_completion_tokens += max(int(completion_tokens), 0)
    totals.llm_calls += 1


def record_embed(*, prompt_tokens: int, calls: int = 1) -> None:
    totals = _current.get()
    if totals is None:
        return
    totals.embed_prompt_tokens += max(int(prompt_tokens), 0)
    totals.embed_calls += max(int(calls), 0)


def _mark_seen(key: str) -> bool:
    totals = _current.get()
    if totals is None or not key or key in totals.seen_ids:
        return False
    totals.seen_ids.add(key)
    return True


def _usage_from_mapping(data: Any) -> tuple[int, int] | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        data = {
            "input_tokens": getattr(data, "input_tokens", None),
            "output_tokens": getattr(data, "output_tokens", None),
            "prompt_eval_count": getattr(data, "prompt_eval_count", None),
            "eval_count": getattr(data, "eval_count", None),
        }
    prompt = data.get("input_tokens")
    if prompt is None:
        prompt = data.get("prompt_eval_count")
    completion = data.get("output_tokens")
    if completion is None:
        completion = data.get("eval_count")
    if prompt is None and completion is None:
        return None
    return int(prompt or 0), int(completion or 0)


def record_from_message(message: Any) -> None:
    """Read Ollama counts off an AIMessage (usage_metadata / response_metadata)."""
    if message is None:
        return
    usage = _usage_from_mapping(getattr(message, "usage_metadata", None))
    if usage is None:
        usage = _usage_from_mapping(getattr(message, "response_metadata", None))
    if usage is None:
        return
    key = str(getattr(message, "id", None) or id(message))
    if not _mark_seen(key):
        return
    record_llm(prompt_tokens=usage[0], completion_tokens=usage[1])


class TokenUsageHandler(BaseCallbackHandler):
    """Collect Ollama prompt_eval_count / eval_count from LangChain chat calls."""

    def __init__(self) -> None:
        super().__init__()
        self._seen: set[str] = set()

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self._ingest_llm_result(response, kwargs.get("run_id"))

    def on_chat_model_end(self, response: LLMResult, **kwargs: Any) -> None:
        self._ingest_llm_result(response, kwargs.get("run_id"))

    def _ingest_llm_result(self, response: LLMResult, run_id: Any) -> None:
        for gens in response.generations:
            for gen in gens:
                message = getattr(gen, "message", None)
                if message is not None:
                    record_from_message(message)
                    continue
                key = str(run_id or id(gen))
                if key in self._seen or not _mark_seen(key):
                    continue
                self._seen.add(key)
                usage = _usage_from_mapping(gen.generation_info)
                if usage is None:
                    usage = _usage_from_mapping(getattr(response, "llm_output", None))
                if usage is not None:
                    record_llm(prompt_tokens=usage[0], completion_tokens=usage[1])


class TrackedOllamaEmbeddings(OllamaEmbeddings):
    """Same embed API, plus Ollama prompt_eval_count when the server reports it."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not self._client:
            raise RuntimeError("Ollama sync client is not initialized.")
        raw = self._client.embed(
            self.model,
            texts,
            dimensions=self.dimensions,
            options=self._default_params,
            keep_alive=self.keep_alive,
        )
        prompt_tokens = int(
            getattr(raw, "prompt_eval_count", None) or raw.get("prompt_eval_count") or 0
        )
        if prompt_tokens == 0:
            prompt_tokens = sum(max(len(t.split()), 1) for t in texts)
        record_embed(prompt_tokens=prompt_tokens, calls=1)
        return [list(vec) for vec in raw["embeddings"]]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@lru_cache(maxsize=1)
def tracked_embeddings() -> TrackedOllamaEmbeddings:
    return TrackedOllamaEmbeddings(model=OLLAMA_EMBED_MODEL, base_url=OLLAMA_BASE_URL)
