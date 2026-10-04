"""Layout-aware PDF extraction: page, bbox, and 4-corner polygons.

Pipeline (digital PDFs; no OCR):
1. Drop header/footer bands (painted chrome on the NexCart templates).
2. Read line boxes from PyMuPDF dict mode (x0, y0, x1, y1 in PDF points, origin top-left).
3. Cluster lines into reading-order regions using vertical gap + x-overlap.
4. Split oversized regions so chunks stay near CHUNK_SIZE_TOKENS.
5. Store a closed quadrilateral (TL, TR, BR, BL) plus 0–1 normalized vertices.

Chroma only accepts scalar metadata, so polygons are JSON strings.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf as fitz
import tiktoken
from langchain_core.documents import Document

from ai.ingestion.loaders import CHUNK_SIZE_TOKENS, DOC_TYPES

HEADER_BAND = 40.0
FOOTER_BAND = 32.0
Y_GAP_FACTOR = 1.15
MIN_X_OVERLAP = 0.15
_LIST_ITEM = re.compile(r"^\d+[.)]?\s+\S")

_ENC = tiktoken.get_encoding("cl100k_base")


def _tokens(text: str) -> int:
    return len(_ENC.encode(text))


def polygon_from_bbox(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    """Clockwise quad: top-left, top-right, bottom-right, bottom-left."""
    return [
        [round(x0, 2), round(y0, 2)],
        [round(x1, 2), round(y0, 2)],
        [round(x1, 2), round(y1, 2)],
        [round(x0, 2), round(y1, 2)],
    ]


def normalize_polygon(
    poly: list[list[float]], page_width: float, page_height: float
) -> list[list[float]]:
    pw = page_width or 1.0
    ph = page_height or 1.0
    return [[round(x / pw, 4), round(y / ph, 4)] for x, y in poly]


def union_bbox(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _x_overlap(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    left = max(a[0], b[0])
    right = min(a[2], b[2])
    width = max(a[2] - a[0], b[2] - b[0], 1.0)
    return max(0.0, right - left) / width


Line = tuple[str, tuple[float, float, float, float], float]


def _page_lines(page: fitz.Page) -> list[Line]:
    ph = page.rect.height
    lines: list[Line] = []
    payload = page.get_text("dict")
    for block in payload.get("blocks") or []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            spans = line.get("spans") or []
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue
            x0, y0, x1, y1 = (float(v) for v in line["bbox"])
            if y1 < HEADER_BAND or y0 > ph - FOOTER_BAND:
                continue
            if y0 < HEADER_BAND + 4:
                continue
            if x1 - x0 < 2 or y1 - y0 < 2:
                continue
            size = max((float(span.get("size") or 0) for span in spans), default=0.0)
            lines.append((text, (x0, y0, x1, y1), size))
    lines.sort(key=lambda item: (round(item[1][1], 1), item[1][0]))
    return lines


def _cluster_lines(lines: list[Line]) -> list[list[Line]]:
    if not lines:
        return []
    heights = [b[3] - b[1] for _, b, _ in lines]
    med_h = sorted(heights)[len(heights) // 2]
    gap_limit = max(8.0, med_h * Y_GAP_FACTOR)
    wrap_limit = max(4.0, med_h * 0.55)
    clusters: list[list[Line]] = [[lines[0]]]
    for item in lines[1:]:
        prev = clusters[-1][-1]
        same_row = abs(item[1][1] - prev[1][1]) <= 4.0
        dy = item[1][1] - prev[1][3]
        heading = item[2] >= 11.5 and item[2] > prev[2] + 0.5
        list_item = bool(_LIST_ITEM.match(item[0]))
        new_paragraph = (
            prev[0].rstrip().endswith((".", "?", ":"))
            and item[0][:1].isupper()
            and dy > wrap_limit
        )
        if heading:
            clusters.append([item])
        elif list_item and not same_row:
            clusters.append([item])
        elif new_paragraph:
            clusters.append([item])
        elif same_row or (dy < gap_limit and _x_overlap(prev[1], item[1]) >= MIN_X_OVERLAP):
            clusters[-1].append(item)
        else:
            clusters.append([item])
    return clusters


def _split_cluster(
    cluster: list[Line],
    max_tokens: int = CHUNK_SIZE_TOKENS,
) -> list[list[Line]]:
    parts: list[list[Line]] = []
    current: list[Line] = []
    for item in cluster:
        trial = current + [item]
        text = "\n".join(t for t, *_ in trial)
        if current and _tokens(text) > max_tokens:
            parts.append(current)
            current = [item]
        else:
            current = trial
    if current:
        parts.append(current)
    return parts


def layout_metadata(
    *,
    source_file: str,
    doc_type: str,
    chunk_index: int,
    page: int,
    page_width: float,
    page_height: float,
    bbox: tuple[float, float, float, float],
) -> dict:
    x0, y0, x1, y1 = (round(v, 2) for v in bbox)
    poly = polygon_from_bbox(x0, y0, x1, y1)
    poly_n = normalize_polygon(poly, page_width, page_height)
    return {
        "source": source_file,
        "source_file": source_file,
        "doc_type": doc_type,
        "chunk_index": chunk_index,
        "page": page,
        "page_width": round(page_width, 2),
        "page_height": round(page_height, 2),
        "bbox_x0": x0,
        "bbox_y0": y0,
        "bbox_x1": x1,
        "bbox_y1": y1,
        "polygon": json.dumps(poly),
        "polygon_norm": json.dumps(poly_n),
        "extraction": "pymupdf_line_clusters",
    }


def parse_layout(metadata: dict) -> dict:
    """Rehydrate layout fields from Chroma scalar metadata."""
    page_raw = metadata.get("page")
    try:
        page = int(page_raw) if page_raw not in (None, "") else None
    except (TypeError, ValueError):
        page = None
    def _f(key: str) -> float | None:
        val = metadata.get(key)
        try:
            return float(val) if val not in (None, "") else None
        except (TypeError, ValueError):
            return None

    bbox = None
    raw_bbox = metadata.get("bbox")
    if isinstance(raw_bbox, dict) and all(k in raw_bbox for k in ("x0", "y0", "x1", "y1")):
        try:
            bbox = {k: float(raw_bbox[k]) for k in ("x0", "y0", "x1", "y1")}
        except (TypeError, ValueError):
            bbox = None
    if bbox is None:
        x0, y0, x1, y1 = _f("bbox_x0"), _f("bbox_y0"), _f("bbox_x1"), _f("bbox_y1")
        if None not in (x0, y0, x1, y1):
            bbox = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
    polygon_raw = metadata.get("polygon") or "[]"
    if isinstance(polygon_raw, list):
        polygon = polygon_raw
    else:
        try:
            polygon = json.loads(polygon_raw)
        except json.JSONDecodeError:
            polygon = []
    polygon_norm_raw = metadata.get("polygon_norm") or "[]"
    if isinstance(polygon_norm_raw, list):
        polygon_norm = polygon_norm_raw
    else:
        try:
            polygon_norm = json.loads(polygon_norm_raw)
        except json.JSONDecodeError:
            polygon_norm = []
    points = []
    for p in polygon:
        if isinstance(p, dict) and "x" in p and "y" in p:
            points.append({"x": float(p["x"]), "y": float(p["y"])})
        elif isinstance(p, list) and len(p) == 2:
            points.append({"x": p[0], "y": p[1]})
    points_n = []
    for p in polygon_norm:
        if isinstance(p, dict) and "x" in p and "y" in p:
            points_n.append({"x": float(p["x"]), "y": float(p["y"])})
        elif isinstance(p, list) and len(p) == 2:
            points_n.append({"x": p[0], "y": p[1]})
    return {
        "page": page,
        "page_width": _f("page_width"),
        "page_height": _f("page_height"),
        "bbox": bbox,
        "polygon": points,
        "polygon_norm": points_n,
        "extraction": metadata.get("extraction"),
    }


def extract_pdf(path: Path | str) -> list[Document]:
    pdf_path = Path(path)
    source_file = pdf_path.name
    doc_type = DOC_TYPES.get(source_file, "other")
    opened = fitz.open(pdf_path)
    documents: list[Document] = []
    try:
        for page in opened:
            page_num = page.number + 1
            pw, ph = float(page.rect.width), float(page.rect.height)
            clusters = _cluster_lines(_page_lines(page))
            for cluster in clusters:
                for part in _split_cluster(cluster):
                    text = "\n".join(t for t, *_ in part).strip()
                    heading_part = any(size >= 11.5 for _, _, size in part)
                    if len(text) < (18 if heading_part else 40):
                        continue
                    bbox = union_bbox([b for _, b, *_ in part])
                    documents.append(
                        Document(
                            page_content=text,
                            metadata=layout_metadata(
                                source_file=source_file,
                                doc_type=doc_type,
                                chunk_index=len(documents),
                                page=page_num,
                                page_width=pw,
                                page_height=ph,
                                bbox=bbox,
                            ),
                        )
                    )
    finally:
        opened.close()
    for i, document in enumerate(documents):
        document.metadata["chunk_index"] = i
    return documents


def extract_pdfs(pdf_dir: Path | str) -> list[Document]:
    directory = Path(pdf_dir)
    files = sorted(directory.glob("*.pdf"))
    if not files:
        raise FileNotFoundError(f"No PDF files found in {directory.resolve()}")
    chunks: list[Document] = []
    for pdf in files:
        chunks.extend(extract_pdf(pdf))
    for i, document in enumerate(chunks):
        document.metadata["chunk_index"] = i
    return chunks
