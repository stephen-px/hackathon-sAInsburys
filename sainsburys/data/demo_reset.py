"""
Reset to a clean demo state.

  python sainsburys/data/demo_reset.py

What it does:
  1. Wipes and recreates the schema (calls seed.seed())
  2. Creates this week's single basket order with realistic lines
  3. Fills inventory_lots with realistic expiry dates for the fridge demo

No fabricated people or events — the leaderboard and activity feed only ever
show real users doing real taps.

Safe to re-run — seed() drops everything first.
"""
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import seed  # sibling module

DB_PATH = Path(__file__).parent / "lunch.db"
TODAY = date(2026, 7, 22)          # Wednesday of demo week
MONDAY = date(2026, 7, 21)         # Monday of demo week


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn


def _pid(conn, name):
    """Return product id by (partial) name, or None."""
    row = conn.execute(
        "SELECT id FROM products WHERE name LIKE ? LIMIT 1", (f"%{name}%",)
    ).fetchone()
    return row["id"] if row else None


def insert_order(conn):
    """This week's single basket order with realistic lines."""
    order_id = conn.execute(
        "INSERT INTO orders (week, delivery_date, status) VALUES (?,?,?) RETURNING id",
        (str(MONDAY), str(MONDAY), "open"),
    ).fetchone()["id"]

    lines = [
        ("Mixed Leaf Salad",     8,  1.10),
        ("Hummus 200g",          6,  1.35),
        ("Cooked Chicken Breast",6,  2.20),
        ("Soft Flour Tortilla",  4,  1.35),
        ("Ready Salted Crisps",  4,  1.75),
        ("Sparkling Water",      4,  2.50),
        ("Caesar Salad Kit",     6,  2.50),
        ("Smoked Salmon 100g",   4,  3.50),
        ("Greek Salad Kit",      4,  2.20),
    ]
    for name, qty, price in lines:
        pid = _pid(conn, name)
        if pid:
            conn.execute(
                "INSERT INTO order_lines (order_id, product_id, qty, unit_price) VALUES (?,?,?,?)",
                (order_id, pid, qty, price),
            )

    print(f"  inserted 1 basket order (id={order_id})")
    return order_id


def insert_lots(conn):
    """
    Create inventory_lots for items currently in the fridge.
    Expiry dates are relative to TODAY so the rescue board always looks fresh.
    """
    lots = [
        # (product_name_fragment, delivery_date, expiry_days_from_today, qty_delivered, qty_remaining)
        ("Hummus 200g",          MONDAY,              0,  6, 2),   # expiring TODAY
        ("Mixed Leaf Salad 100g",MONDAY,              1,  8, 3),   # 1 day left
        ("Cooked Chicken Breast",MONDAY,              2,  6, 1),   # 2 days left
        ("Greek Salad Kit",      MONDAY,              2,  4, 4),   # 2 days left
        ("Guacamole",            MONDAY,              3,  4, 2),   # 3 days left
        ("Soft Flour Tortilla",  MONDAY,              4,  4, 5),   # 4 days left
        ("Ready Salted Crisps",  MONDAY,             12,  4, 4),   # shelf-stable, plenty left
    ]
    lot_ids = []
    for name, delivery, days_from_today, qty_del, qty_rem in lots:
        pid = _pid(conn, name)
        if not pid:
            print(f"  WARNING: product not found for '{name}'")
            continue
        expiry = TODAY + timedelta(days=days_from_today)
        row = conn.execute(
            "INSERT INTO inventory_lots "
            "(product_id, delivery_date, expiry_date, qty_delivered, qty_remaining) "
            "VALUES (?,?,?,?,?) RETURNING id",
            (pid, str(delivery), str(expiry), qty_del, qty_rem),
        ).fetchone()
        lot_ids.append((row["id"], name, pid))

    print(f"  inserted {len(lot_ids)} inventory lots")
    return lot_ids


def main():
    print("Resetting demo DB…")
    seed.seed()

    conn = _conn()
    with conn:
        insert_order(conn)
        insert_lots(conn)
    conn.close()

    print("Done. Run: python sainsburys/dashboard/api.py")
    print("  or:  docker compose up --build")


if __name__ == "__main__":
    main()
