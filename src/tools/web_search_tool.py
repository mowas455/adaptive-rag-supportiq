"""Web search fallback: DuckDuckGo by default, Tavily if configured."""

from __future__ import annotations

from typing import Any

from src.config import TAVILY_API_KEY, WEB_SEARCH_PROVIDER


def search_web(query: str, *, max_results: int = 5) -> list[dict[str, str]]:
    provider = WEB_SEARCH_PROVIDER
    try:
        if provider == "tavily" and TAVILY_API_KEY:
            return _tavily_search(query, max_results=max_results)
        return _duckduckgo_search(query, max_results=max_results)
    except Exception as exc:  # noqa: BLE001 — fallback must never crash the graph
        return [
            {
                "title": "Web search error",
                "url": "",
                "snippet": f"Search failed ({type(exc).__name__}): {exc}",
            }
        ]


def format_results(results: list[dict[str, str]]) -> str:
    if not results:
        return "No web search results were found."
    blocks = []
    for i, item in enumerate(results, 1):
        title = item.get("title") or "(no title)"
        url = item.get("url") or ""
        snippet = item.get("snippet") or ""
        blocks.append(f"[{i}] {title}\nURL: {url}\n{snippet}")
    return "\n\n".join(blocks)


def _duckduckgo_search(query: str, *, max_results: int) -> list[dict[str, str]]:
    from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

    wrapper = DuckDuckGoSearchAPIWrapper(max_results=max_results, time="m")
    raw: list[dict[str, Any]] = wrapper.results(query, max_results=max_results)
    out: list[dict[str, str]] = []
    for item in raw:
        out.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("link") or item.get("href") or ""),
                "snippet": str(item.get("snippet") or item.get("body") or ""),
            }
        )
    return out


def _tavily_search(query: str, *, max_results: int) -> list[dict[str, str]]:
    from tavily import TavilyClient

    client = TavilyClient(api_key=TAVILY_API_KEY)
    payload = client.search(query, max_results=max_results)
    out: list[dict[str, str]] = []
    for item in payload.get("results", []):
        out.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("content") or ""),
            }
        )
    return out
