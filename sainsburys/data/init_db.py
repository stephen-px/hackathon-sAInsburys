"""
Create the SQLite schema and seed reference data.
Run once before starting the app: python sainsburys/data/init_db.py

Idempotent — safe to re-run; uses CREATE TABLE IF NOT EXISTS.
To wipe and reseed, delete sainsburys/data/lunch.db first.
"""
import csv
import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("LUNCH_DB", str(Path(__file__).parent / "lunch.db"))


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma journal_mode = wal")  # safe for multi-reader
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    slack_id  TEXT PRIMARY KEY,
    name      TEXT,
    dietary   TEXT DEFAULT '[]',   -- JSON array
    taste     TEXT DEFAULT '{}'    -- JSON object
);

CREATE TABLE IF NOT EXISTS products (
    id               INTEGER PRIMARY KEY,
    name             TEXT,
    category         TEXT,
    price            REAL,
    shelf_life_days  INTEGER,
    url              TEXT
);

CREATE TABLE IF NOT EXISTS meals (
    id          INTEGER PRIMARY KEY,
    name        TEXT,
    description TEXT,
    tags        TEXT DEFAULT '[]'  -- JSON array
);

CREATE TABLE IF NOT EXISTS meal_products (
    meal_id    INTEGER REFERENCES meals(id),
    product_id INTEGER REFERENCES products(id),
    qty        REAL
);

CREATE TABLE IF NOT EXISTS selections (
    id             INTEGER PRIMARY KEY,
    week           TEXT,
    half           TEXT CHECK(half IN ('early','late')),
    user_slack_id  TEXT REFERENCES users(slack_id),
    meal_id        INTEGER REFERENCES meals(id),
    freeform       TEXT,
    parsed         TEXT,           -- JSON
    status         TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY,
    week          TEXT,
    delivery_date TEXT,
    status        TEXT DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS order_lines (
    order_id   INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    qty        REAL,
    unit_price REAL
);

CREATE TABLE IF NOT EXISTS inventory_lots (
    id            INTEGER PRIMARY KEY,
    product_id    INTEGER REFERENCES products(id),
    delivery_date TEXT,
    expiry_date   TEXT,
    qty_delivered REAL,
    qty_remaining REAL
);

CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY,
    ts            DATETIME DEFAULT CURRENT_TIMESTAMP,
    kind          TEXT CHECK(kind IN ('consumed','claimed','wasted')),
    user_slack_id TEXT,
    lot_id        INTEGER REFERENCES inventory_lots(id),
    qty           REAL,
    value         REAL
);
"""

VIEWS = """
DROP VIEW IF EXISTS leftovers;
CREATE VIEW leftovers AS
    SELECT l.*, p.name, p.price,
           CAST(julianday(l.expiry_date) - julianday('now') AS INTEGER) AS days_left
    FROM inventory_lots l
    JOIN products p ON p.id = l.product_id
    WHERE l.qty_remaining > 0;

DROP VIEW IF EXISTS leaderboard;
CREATE VIEW leaderboard AS
    SELECT user_slack_id, SUM(value) AS saved
    FROM events
    WHERE kind = 'claimed'
    GROUP BY user_slack_id
    ORDER BY saved DESC;

DROP VIEW IF EXISTS weekly_totals;
CREATE VIEW weekly_totals AS
    SELECT strftime('%Y-%m-%d', datetime(ts, 'weekday 1', '-7 days')) AS week,
           kind,
           SUM(value) AS total
    FROM events
    GROUP BY week, kind;
"""


def seed_products(conn):
    cur = conn.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] > 0:
        return  # already seeded

    catalogue_path = Path(__file__).parent / "catalogue.csv"
    with open(catalogue_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = [
            (row["name"], row["category"], float(row["price"]),
             int(row["shelf_life_days"]), row.get("url") or None)
            for row in reader
        ]
    conn.executemany(
        "INSERT INTO products (name, category, price, shelf_life_days, url) VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    print(f"  seeded {len(rows)} products")


def main():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    print(f"Initialising DB at {DB_PATH}")
    conn = _conn()
    for stmt in SCHEMA.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    print("  schema created")

    # Views need to be executed individually
    for stmt in VIEWS.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    print("  views created")

    seed_products(conn)
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
