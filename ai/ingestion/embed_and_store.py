"""Embed knowledge-base chunks into the configured vector index and seed orders."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.config import DOCS_DIR, ORDERS_DB, PDF_DIR, VECTOR_BACKEND  # noqa: E402
from ai.ingestion.loaders import load_and_chunk  # noqa: E402
from ai.ingestion.seed_orders import seed_orders_db  # noqa: E402
from ai.retrieval.store import get_vector_index, reset_vectorstore_cache  # noqa: E402


def ingest(
    docs_dir: Path | None = None,
    persist_dir: Path | None = None,
    collection_name: str | None = None,
    orders_db: Path | None = None,
    reset_chroma: bool = True,
) -> dict:
    """Run ingest into Chroma or Supabase based on VECTOR_BACKEND."""
    load_dotenv(ROOT / ".env")
    reset_vectorstore_cache()

    documents = load_and_chunk(docs_dir or DOCS_DIR, pdf_dir=PDF_DIR)
    index = get_vector_index()
    collection_size = index.upsert(documents, reset=reset_chroma)
    order_count = seed_orders_db(orders_db or ORDERS_DB)

    summary = {
        "source_files": sorted({d.metadata.get("source_file", "?") for d in documents}),
        "chunk_count": len(documents),
        "collection_name": index.name,
        "collection_size": collection_size,
        "persist_dir": str(persist_dir) if persist_dir else VECTOR_BACKEND,
        "vector_backend": VECTOR_BACKEND,
        "orders_db": str(orders_db or ORDERS_DB),
        "order_count": order_count,
    }
    return summary


def print_summary(summary: dict) -> None:
    print("=== SupportIQ ingestion complete ===")
    print(f"Source files     : {', '.join(summary['source_files'])}")
    print(f"Chunk count      : {summary['chunk_count']}")
    print(f"Vector backend   : {summary.get('vector_backend') or summary['collection_name']}")
    print(f"Collection size  : {summary['collection_size']}")
    print(f"Orders DB        : {summary['orders_db']} ({summary['order_count']} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest docs into the vector index and seed orders.db")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not wipe the existing index before ingesting",
    )
    args = parser.parse_args()
    summary = ingest(reset_chroma=not args.no_reset)
    print_summary(summary)


if __name__ == "__main__":
    main()
