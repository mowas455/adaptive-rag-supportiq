"""Seed the mock SQLite orders table used by the sql_lookup graph node."""

from __future__ import annotations

import sqlite3
from pathlib import Path

ORDERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    customer_email TEXT NOT NULL,
    status TEXT NOT NULL,
    eta TEXT,
    items TEXT NOT NULL
);
"""

# ~10 realistic rows, including order 4521 from the project brief.
SEED_ORDERS: list[tuple[str, str, str, str | None, str]] = [
    ("4521", "alex.nguyen@example.com", "shipped", "2026-09-16", "PulseBuds (black); USB-C cable"),
    ("4522", "priya.desai@example.com", "delivered", "2026-09-08", "GlowBar LED strip 2m"),
    ("4523", "jordan.lee@example.com", "processing", "2026-09-18", "HomePlug mini 2-pack"),
    ("4524", "sam.okonkwo@example.com", "out_for_delivery", "2026-09-13", "LockStep deadbolt; AA lithium 8-pack"),
    ("4525", "morgan.chen@example.com", "cancelled", None, "NexCart Plus annual (promo)"),
    ("4526", "riley.patel@example.com", "returned", "2026-09-05", "PulseBuds (white)"),
    ("4527", "casey.brooks@example.com", "backordered", "2026-09-29", "GlowBar LED strip 5m"),
    ("4528", "taylor.kim@example.com", "shipped", "2026-09-15", "HomePlug mini; GlowBar clips"),
    ("4529", "avery.hassan@example.com", "delivered", "2026-09-10", "LockStep deadbolt"),
    ("4530", "jamie.foster@example.com", "processing", "2026-09-19", "PulseBuds (black); carrying case"),
]


def seed_orders_db(db_path: str | Path) -> int:
    """Create/replace the orders table and insert seed rows. Returns row count."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        conn.execute("DROP TABLE IF EXISTS orders")
        conn.execute(ORDERS_SCHEMA)
        conn.executemany(
            """
            INSERT INTO orders (order_id, customer_email, status, eta, items)
            VALUES (?, ?, ?, ?, ?)
            """,
            SEED_ORDERS,
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    finally:
        conn.close()
    return int(count)
