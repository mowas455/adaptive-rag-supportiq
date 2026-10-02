"""Ollama chat helper with Pydantic structured output."""

from __future__ import annotations

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from ai.config import OLLAMA_BASE_URL, OLLAMA_LLM_MODEL
from ai.observability.usage import record_from_message


def get_llm(*, temperature: float = 0.0) -> ChatOllama:
    return ChatOllama(
        model=OLLAMA_LLM_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
    )


def structured_invoke(
    schema: type[BaseModel],
    messages: list[BaseMessage] | list[tuple[str, str]],
    *,
    temperature: float = 0.0,
    config: RunnableConfig | None = None,
) -> BaseModel:
    """Run an LLM call that must return ``schema``. Raises on parse failure."""
    llm = get_llm(temperature=temperature)
    runnable = llm.with_structured_output(schema, method="json_schema", include_raw=True)
    payload = runnable.invoke(messages, config=config)
    if isinstance(payload, dict):
        record_from_message(payload.get("raw"))
        parsed = payload.get("parsed")
        if isinstance(parsed, schema):
            return parsed
        if parsed is not None:
            return schema.model_validate(parsed)
        raise ValueError(f"Failed to parse {schema.__name__} from llama3.2")
    if not isinstance(payload, schema):
        payload = schema.model_validate(payload)
    return payload
