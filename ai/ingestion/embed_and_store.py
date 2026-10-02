"""Embed knowledge-base chunks into local Chroma and seed the orders SQLite DB."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.ingestion.loaders import load_and_chunk  # noqa: E402
from ai.ingestion.seed_orders import seed_orders_db  # noqa: E402


def _env_path(name: str, default: str) -> Path:
    import os

    raw = os.getenv(name, default)
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def ingest(
    docs_dir: Path | None = None,
    persist_dir: Path | None = None,
    collection_name: str | None = None,
    orders_db: Path | None = None,
    reset_chroma: bool = True,
) -> dict:
    """Run the full Phase 1 pipeline. Returns a summary dict."""
    import os

    load_dotenv(ROOT / ".env")

    docs_dir = docs_dir or _env_path("DOCS_DIR", "data/docs")
    pdf_dir = _env_path("PDF_DIR", "data/pdfs")
    persist_dir = persist_dir or _env_path("CHROMA_PERSIST_DIR", "chroma_db")
    collection_name = collection_name or os.getenv("CHROMA_COLLECTION", "supportiq")
    orders_db = orders_db or _env_path("ORDERS_DB", "data/orders.db")
    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    documents = load_and_chunk(docs_dir, pdf_dir=pdf_dir)

    if reset_chroma and persist_dir.exists():
        shutil.rmtree(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    embeddings = OllamaEmbeddings(model=embed_model, base_url=ollama_url)
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=str(persist_dir),
        collection_name=collection_name,
    )
    collection_size = vectorstore._collection.count()  # noqa: SLF001

    order_count = seed_orders_db(orders_db)

    summary = {
        "source_files": sorted({d.metadata.get("source_file", "?") for d in documents}),
        "chunk_count": len(documents),
        "collection_name": collection_name,
        "collection_size": collection_size,
        "persist_dir": str(persist_dir),
        "orders_db": str(orders_db),
        "order_count": order_count,
        "embed_model": embed_model,
    }
    return summary


def print_summary(summary: dict) -> None:
    print("=== SupportIQ ingestion complete ===")
    print(f"Source files     : {', '.join(summary['source_files'])}")
    print(f"Chunk count      : {summary['chunk_count']}")
    print(f"Chroma collection: {summary['collection_name']} ({summary['collection_size']} vectors)")
    print(f"Persist dir      : {summary['persist_dir']}")
    print(f"Orders DB        : {summary['orders_db']} ({summary['order_count']} rows)")
    print(f"Embedding model  : {summary['embed_model']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest docs into Chroma and seed orders.db")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not delete the existing Chroma directory before ingesting",
    )
    args = parser.parse_args()
    summary = ingest(reset_chroma=not args.no_reset)
    print_summary(summary)


if __name__ == "__main__":
    main()
