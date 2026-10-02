"""Render a PDF page from data/pdfs with the citation rectangle on top."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from ai.config import PDF_DIR


def resolve_pdf(source: str) -> Path:
    name = Path(source).name
    if name != source.replace("\\", "/").split("/")[-1] or ".." in name:
        raise FileNotFoundError("Invalid PDF name")
    path = (PDF_DIR / name).resolve()
    pdf_root = PDF_DIR.resolve()
    if pdf_root not in path.parents and path != pdf_root:
        raise FileNotFoundError(name)
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise FileNotFoundError(name)
    return path


def render_page_preview(
    source: str,
    page: int,
    *,
    x0: float | None = None,
    y0: float | None = None,
    x1: float | None = None,
    y1: float | None = None,
    scale: float = 1.7,
) -> bytes:
    """Return PNG bytes of ``page`` (1-based) with an optional highlight bbox."""
    path = resolve_pdf(source)
    src = pymupdf.open(path)
    try:
        index = page - 1
        if index < 0 or index >= src.page_count:
            raise IndexError(f"page {page} out of range")
        overlay = pymupdf.open()
        overlay.insert_pdf(src, from_page=index, to_page=index)
    finally:
        src.close()
    try:
        leaf = overlay[0]
        if None not in (x0, y0, x1, y1):
            rect = pymupdf.Rect(float(x0), float(y0), float(x1), float(y1))
            rect = rect & leaf.rect
            if not rect.is_empty:
                shape = leaf.new_shape()
                shape.draw_rect(rect)
                shape.finish(
                    color=(0.85, 0.45, 0.05),
                    fill=(1.0, 0.78, 0.2),
                    fill_opacity=0.28,
                    width=1.6,
                )
                shape.commit()
        pix = leaf.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        return pix.tobytes("png")
    finally:
        overlay.close()
