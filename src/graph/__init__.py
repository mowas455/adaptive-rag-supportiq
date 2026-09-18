"""LangGraph package."""

from __future__ import annotations

from typing import Any

__all__ = ["build_graph", "get_graph", "run_supportiq"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from src.graph.build_graph import build_graph, get_graph, run_supportiq

        return {
            "build_graph": build_graph,
            "get_graph": get_graph,
            "run_supportiq": run_supportiq,
        }[name]
    raise AttributeError(name)
