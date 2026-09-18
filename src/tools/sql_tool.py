"""Structured order lookup against the mock SQLite orders table."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from src.config import ORDERS_DB

ORDER_ID_RE = re.compile(r"\b(?:order\s*#?\s*)?(\d{4,6})\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def extract_order_id(text: str) -> str | None:
    match = ORDER_ID_RE.search(text)
    return match.group(1) if match else None


def extract_email(text: str) -> str | None:
    match = EMAIL_RE.search(text)
    return match.group(0).lower() if match else None


def lookup_orders(
    *,
    order_id: str | None = None,
    customer_email: str | None = None,
) -> list[dict[str, Any]]:
    if not order_id and not customer_email:
        return []

    clauses: list[str] = []
    params: list[str] = []
    if order_id:
        clauses.append("order_id = ?")
        params.append(str(order_id).lstrip("#"))
    if customer_email:
        clauses.append("LOWER(customer_email) = LOWER(?)")
        params.append(customer_email)

    sql = (
        "SELECT order_id, customer_email, status, eta, items FROM orders WHERE "
        + " OR ".join(clauses)
    )
    conn = sqlite3.connect(ORDERS_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def format_orders(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No matching orders were found in the orders database."
    blocks = []
    for row in rows:
        eta = row.get("eta") or "not listed"
        blocks.append(
            "Structured order record (not live GPS). Use only these fields:\n"
            f"- order_id: {row['order_id']}\n"
            f"- customer_email: {row['customer_email']}\n"
            f"- status: {row['status']}\n"
            f"- estimated_delivery (ETA): {eta}\n"
            f"- items: {row['items']}\n"
            "No ship date or tracking number is available beyond status and ETA."
        )
    return "\n\n".join(blocks)
