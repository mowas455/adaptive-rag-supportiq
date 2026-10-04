"""Vector index switch: VECTOR_BACKEND=chroma | supabase."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Protocol

from langchain_chroma import Chroma
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from ai.config import (
    CHROMA_COLLECTION,
    CHROMA_PERSIST_DIR,
    VECTOR_BACKEND,
)
from ai.observability.usage import tracked_embeddings

Hit = tuple[str, dict]
_TOKEN = re.compile(r"[a-z0-9]+")


class VectorIndex(Protocol):
    name: str

    def upsert(self, documents: list[Document], *, reset: bool = True) -> int: ...
    def similarity_search(self, query: str, k: int) -> list[Hit]: ...
    def lexical_search(self, query: str, k: int) -> list[Hit]: ...
    def count(self) -> int: ...


class ChromaIndex:
    name = "chroma"

    def __init__(self) -> None:
        self._embeddings = tracked_embeddings()
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        self._store = Chroma(
            persist_directory=str(CHROMA_PERSIST_DIR),
            collection_name=CHROMA_COLLECTION,
            embedding_function=self._embeddings,
        )

    def upsert(self, documents: list[Document], *, reset: bool = True) -> int:
        import shutil

        if reset and CHROMA_PERSIST_DIR.exists():
            shutil.rmtree(CHROMA_PERSIST_DIR)
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        self._store = Chroma.from_documents(
            documents=documents,
            embedding=self._embeddings,
            persist_directory=str(CHROMA_PERSIST_DIR),
            collection_name=CHROMA_COLLECTION,
        )
        return self.count()

    def similarity_search(self, query: str, k: int) -> list[Hit]:
        docs = self._store.similarity_search(query, k=k)
        return [(d.page_content, dict(d.metadata)) for d in docs]

    def lexical_search(self, query: str, k: int) -> list[Hit]:
        raw = self._store._collection.get(include=["documents", "metadatas"])  # noqa: SLF001
        corpus = list(raw.get("documents") or [])
        metadatas = list(raw.get("metadatas") or [])
        if not corpus:
            return []
        bm25 = BM25Okapi([_TOKEN.findall(doc.lower()) for doc in corpus])
        scores = bm25.get_scores(_TOKEN.findall(query.lower()))
        ranked = sorted(range(len(corpus)), key=lambda i: float(scores[i]), reverse=True)[:k]
        return [(corpus[i], dict(metadatas[i] or {})) for i in ranked]

    def count(self) -> int:
        return int(self._store._collection.count())  # noqa: SLF001


@lru_cache(maxsize=1)
def get_vector_index() -> VectorIndex:
    if VECTOR_BACKEND == "supabase":
        from ai.retrieval.supabase_store import SupabaseIndex

        return SupabaseIndex()
    if VECTOR_BACKEND not in {"chroma", "supabase"}:
        raise ValueError(f"VECTOR_BACKEND must be chroma or supabase, got {VECTOR_BACKEND!r}")
    return ChromaIndex()


def reset_vectorstore_cache() -> None:
    get_vector_index.cache_clear()
