"""Ollama chat helper with Pydantic structured output."""

from __future__ import annotations

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from src.config import OLLAMA_BASE_URL, OLLAMA_LLM_MODEL


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
    runnable = llm.with_structured_output(schema, method="json_schema")
    result = runnable.invoke(messages, config=config)
    if not isinstance(result, schema):
        result = schema.model_validate(result)
    return result
