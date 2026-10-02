"""Load markdown knowledge-base files and split them into overlapping chunks."""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

DOC_TYPES = {
    "return_policy.md": "policy",
    "shipping_faq.md": "shipping",
    "product_troubleshooting.md": "troubleshooting",
    "account_billing_faq.md": "billing",
    "glowbar_product_manual.md": "product",
}

CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50


def load_documents(docs_dir: str | Path) -> list[Document]:
    """Load all .md / .txt files under ``docs_dir`` (non-recursive by default)."""
    path = Path(docs_dir)
    if not path.exists():
        raise FileNotFoundError(f"Docs directory not found: {path.resolve()}")

    loader = DirectoryLoader(
        str(path),
        glob="*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=False,
        use_multithreading=False,
    )
    documents = loader.load()
    if not documents:
        raise ValueError(f"No markdown files found in {path.resolve()}")
    return documents


def chunk_documents(documents: list[Document]) -> list[Document]:
    """Split documents with RecursiveCharacterTextSplitter at ~500 token chunks."""
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    for i, chunk in enumerate(chunks):
        source = Path(str(chunk.metadata.get("source", "unknown"))).name
        chunk.metadata["chunk_index"] = i
        chunk.metadata["source_file"] = source
        chunk.metadata["doc_type"] = DOC_TYPES.get(source, "other")
    return chunks


def load_and_chunk(docs_dir: str | Path) -> list[Document]:
    return chunk_documents(load_documents(docs_dir))
