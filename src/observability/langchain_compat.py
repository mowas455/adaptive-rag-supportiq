"""Shims so langfuse==2 can import LangChain 1.x (callbacks/schema moved)."""

from __future__ import annotations

import sys
import types


def install_langchain_v1_shims() -> None:
    if "langchain.callbacks.base" in sys.modules:
        return

    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.documents import Document

    try:
        from langchain_core.agents import AgentAction, AgentFinish
    except ImportError:  # pragma: no cover
        AgentAction = type("AgentAction", (), {})  # type: ignore[misc,assignment]
        AgentFinish = type("AgentFinish", (), {})  # type: ignore[misc,assignment]

    schema = types.ModuleType("langchain.schema")
    schema_agent = types.ModuleType("langchain.schema.agent")
    schema_agent.AgentAction = AgentAction
    schema_agent.AgentFinish = AgentFinish
    schema_doc = types.ModuleType("langchain.schema.document")
    schema_doc.Document = Document
    schema.agent = schema_agent
    schema.document = schema_doc

    callbacks = types.ModuleType("langchain.callbacks")
    callbacks_base = types.ModuleType("langchain.callbacks.base")
    callbacks_base.BaseCallbackHandler = BaseCallbackHandler
    callbacks.base = callbacks_base

    sys.modules.setdefault("langchain.schema", schema)
    sys.modules.setdefault("langchain.schema.agent", schema_agent)
    sys.modules.setdefault("langchain.schema.document", schema_doc)
    sys.modules.setdefault("langchain.callbacks", callbacks)
    sys.modules.setdefault("langchain.callbacks.base", callbacks_base)
