"""
Reset to a clean, realistic demo state.

  python sainsburys/data/demo_reset.py

What it does:
  1. Wipes and recreates the schema (calls seed.seed())
  2. Inserts 5 demo users
  3. Creates this week's two orders (Mon approved, Wed draft) with realistic lines
  4. Delivers the Monday order into inventory_lots with realistic expiry dates
  5. Inserts 4 weeks of events so the chart, leaderboard, and stats all show real data

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


def insert_users(conn):
    users = [
        ("U001", "Alice Chen",   '["vegetarian"]',         '{"wrap":3,"salad":2}'),
        ("U002", "Bob Smith",    '[]',                     '{"chicken":4,"sandwich":2}'),
        ("U003", "Carol Jones",  '["gluten-free"]',        '{"salad":3,"protein":2}'),
        ("U004", "Dave Kumar",   '["vegan"]',              '{"salad":5,"falafel":3}'),
        ("U005", "Eve Williams", '[]',                     '{"salmon":2,"wrap":3}'),
        ("U006", "Frank Lee",    '[]',                     '{"chicken":2,"ready_meal":3}'),
        ("U007", "Grace Park",   '["vegetarian"]',         '{"salad":4,"dairy":2}'),
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO users (slack_id, name, dietary, taste) VALUES (?,?,?,?)",
        users,
    )
    print(f"  inserted {len(users)} users")


def insert_orders_and_lots(conn):
    """Monday (approved+delivered) and Wednesday (draft) orders with realistic lines."""
    wed = MONDAY + timedelta(days=2)

    # Monday order — approved
    mon_id = conn.execute(
        "INSERT INTO orders (week, delivery_date, status) VALUES (?,?,?) RETURNING id",
        (str(MONDAY), str(MONDAY), "approved"),
    ).fetchone()["id"]

    mon_lines = [
        ("Mixed Leaf Salad",     8,  1.10),
        ("Hummus 200g",          6,  1.35),
        ("Cooked Chicken Breast",6,  2.20),
        ("Soft Flour Tortilla",  4,  1.35),
        ("Ready Salted Crisps",  4,  1.75),
        ("Sparkling Water",      4,  2.50),
    ]
    for name, qty, price in mon_lines:
        pid = _pid(conn, name)
        if pid:
            conn.execute(
                "INSERT INTO order_lines (order_id, product_id, qty, unit_price) VALUES (?,?,?,?)",
                (mon_id, pid, qty, price),
            )

    # Wednesday order — draft
    wed_id = conn.execute(
        "INSERT INTO orders (week, delivery_date, status) VALUES (?,?,?) RETURNING id",
        (str(MONDAY), str(wed), "draft"),
    ).fetchone()["id"]

    wed_lines = [
        ("Caesar Salad Kit",     6, 2.50),
        ("Smoked Salmon 100g",   4, 3.50),
        ("Plain Bagels",         4, 1.50),
        ("Chicken Tikka Pieces", 4, 2.50),
        ("Greek Salad Kit",      4, 2.20),
        ("Feta Cheese",          3, 2.50),
    ]
    for name, qty, price in wed_lines:
        pid = _pid(conn, name)
        if pid:
            conn.execute(
                "INSERT INTO order_lines (order_id, product_id, qty, unit_price) VALUES (?,?,?,?)",
                (wed_id, pid, qty, price),
            )

    print(f"  inserted 2 orders (mon approved id={mon_id}, wed draft id={wed_id})")
    return mon_id, wed_id


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


def insert_events(conn, lot_ids):
    """
    Insert 4 weeks of events so the chart, leaderboard, and stats all have real data.
    This week's events use actual lot IDs; older events use lot_id=NULL (still counts for £).
    """
    # lot_id lookup: (name fragment) → lot_id
    lot_map = {name: lid for lid, name, _ in lot_ids}

    def ts(d, h=10, m=0):
        return f"{d}T{h:02d}:{m:02d}:00"

    # ── Past 3 weeks (older events, lot_id NULL — they're gone from the fridge) ──
    past_events = []
    for week_start, week_events in [
        (date(2026, 6, 29), [
            ("claimed",  "U001", 18.50), ("claimed",  "U002", 12.30),
            ("wasted",   None,    8.50), ("consumed", "U003",  4.80),
            ("wasted",   None,   10.00), ("claimed",  "U004",  1.50),
        ]),
        (date(2026, 7, 6), [
            ("claimed",  "U002", 14.20), ("claimed",  "U003", 12.30),
            ("claimed",  "U001",  9.80), ("claimed",  "U005",  4.90),
            ("wasted",   None,    7.30), ("wasted",   None,    5.00),
            ("consumed", "U004",  6.00),
        ]),
        (date(2026, 7, 13), [
            ("claimed",  "U001", 11.20), ("claimed",  "U002",  9.80),
            ("claimed",  "U003",  8.40), ("claimed",  "U006",  5.60),
            ("claimed",  "U004",  3.80), ("wasted",   None,    4.50),
            ("wasted",   None,    5.00), ("consumed", "U005",  3.00),
        ]),
    ]:
        for i, (kind, user, value) in enumerate(week_events):
            past_events.append((
                ts(week_start + timedelta(days=i % 5, hours=9 + i % 3)),
                kind, user, None, 1.0, round(value, 2),
            ))

    # ── This week (Mon + Tue, using real lot IDs) ──
    this_week = [
        # (ts, kind, user, lot_name_fragment, qty, value)
        (ts(MONDAY, 10, 15), "claimed",  "U001", "Hummus 200g",    1, 1.35),
        (ts(MONDAY, 10, 42), "claimed",  "U002", "Cooked Chicken", 1, 2.20),
        (ts(MONDAY, 11, 10), "claimed",  "U003", "Mixed Leaf",     1, 1.10),
        (ts(MONDAY, 12,  5), "claimed",  "U005", "Hummus 200g",    1, 1.35),
        (ts(MONDAY, 12, 30), "consumed", "U006", "Ready Salted",   1, 1.75),
        (ts(TODAY,   9, 20), "claimed",  "U004", "Cooked Chicken", 1, 2.20),
        (ts(TODAY,   9, 55), "claimed",  "U001", "Mixed Leaf",     1, 1.10),
        (ts(TODAY,  10, 15), "claimed",  "U007", "Guacamole",      1, 1.85),
        (ts(TODAY,  10, 50), "wasted",   None,   "Greek Salad",    1, 2.20),
    ]

    conn.executemany(
        "INSERT INTO events (ts, kind, user_slack_id, lot_id, qty, value) VALUES (?,?,?,?,?,?)",
        past_events,
    )

    for row_ts, kind, user, lot_name, qty, value in this_week:
        lid = None
        if lot_name:
            # find matching lot_id
            for k, v in lot_map.items():
                if lot_name.lower() in k.lower():
                    lid = v
                    break
        conn.execute(
            "INSERT INTO events (ts, kind, user_slack_id, lot_id, qty, value) VALUES (?,?,?,?,?,?)",
            (row_ts, kind, user, lid, qty, value),
        )

    total = len(past_events) + len(this_week)
    print(f"  inserted {total} events across 4 weeks")


def main():
    print("Resetting demo DB…")
    seed.seed()

    conn = _conn()
    with conn:
        insert_users(conn)
        insert_orders_and_lots(conn)
        lot_ids = insert_lots(conn)
        insert_events(conn, lot_ids)
    conn.close()

    print("Done. Run: python sainsburys/dashboard/api.py")
    print("  or:  docker compose up --build")


if __name__ == "__main__":
    main()
