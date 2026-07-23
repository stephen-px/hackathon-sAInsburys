"""
Seed the product catalogue and demo meals into SQLite.
Safe to re-run: drops all tables and recreates from schema_sqlite.sql.
Products come from catalogue.csv (extracted from real order receipts).

    python data/seed.py
"""
import csv
import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "lunch.db"
SCHEMA = DATA_DIR / "schema_sqlite.sql"
CATALOGUE = DATA_DIR / "catalogue.csv"


def load_catalogue():
    with open(CATALOGUE, newline="") as f:
        return [
            (row["name"], row["category"], float(row["price"]), int(row["shelf_life_days"]),
             row.get("url") or None, row.get("sainsburys_uid") or None)
            for row in csv.DictReader(f)
        ]

PRODUCTS = load_catalogue()

# Meals defined by product name (resolved to IDs at seed time)
MEALS = [
    {
        "name": "Caesar Wrap",
        "description": "Caesar salad kit in a flour wrap with chicken",
        "tags": ["chicken", "wrap"],
        "products": [
            ("Sainsbury's Caesar Salad Kit 400g",         1),
            ("Sainsbury's Cooked Chicken Breast 125g",    1),
            ("Sainsbury's Soft Flour Tortilla Wraps 8pk", 1),
        ],
    },
    {
        "name": "Prawn Marie Rose Salad",
        "description": "Mixed leaf, prawn cocktail and mayo",
        "tags": ["seafood", "salad", "gluten-free"],
        "products": [
            ("Sainsbury's Mixed Leaf Salad 100g", 1),
            ("Sainsbury's Prawn Cocktail 150g",   1),
            ("Sainsbury's Reduced Fat Mayo 400g", 1),
        ],
    },
    {
        "name": "Smoked Salmon & Avo Bagel",
        "description": "Smoked salmon with guacamole in a plain bagel",
        "tags": ["seafood", "bagel", "no-meat"],
        "products": [
            ("Sainsbury's Smoked Salmon 100g", 1),
            ("Sainsbury's Guacamole 150g",     1),
            ("Sainsbury's Plain Bagels 5pk",   1),
        ],
    },
    {
        "name": "Salmon & Tabbouleh Bowl",
        "description": "Honey roast salmon flakes over tabbouleh",
        "tags": ["seafood", "salad", "no-meat"],
        "products": [
            ("Sainsbury's Honey Roast Salmon Flakes 120g", 1),
            ("Sainsbury's Tabbouleh 300g",                 1),
        ],
    },
    {
        "name": "Chicken Tikka Wrap",
        "description": "Chicken tikka pieces with mixed leaf in a flour wrap",
        "tags": ["chicken", "wrap", "spicy"],
        "products": [
            ("Sainsbury's Chicken Tikka Pieces 150g",     1),
            ("Sainsbury's Mixed Leaf Salad 100g",         1),
            ("Sainsbury's Soft Flour Tortilla Wraps 8pk", 1),
        ],
    },
    {
        "name": "Tuna & Cheese Sandwich",
        "description": "Tuna, cheddar and mayo on white bread",
        "tags": ["fish", "sandwich"],
        "products": [
            ("Sainsbury's Tuna in Spring Water 145g",  1),
            ("Sainsbury's Mature Cheddar Slices 10pk", 1),
            ("Sainsbury's Reduced Fat Mayo 400g",      1),
            ("Sainsbury's Sliced White Bread 800g",    1),
        ],
    },
    {
        "name": "Greek Salad Box",
        "description": "Greek salad kit with feta and hummus pitta dip",
        "tags": ["vegetarian", "salad", "no-meat"],
        "products": [
            ("Sainsbury's Greek Salad Kit 300g",     1),
            ("Sainsbury's Feta Cheese 200g",         1),
            ("Sainsbury's Hummus 200g",              1),
            ("Sainsbury's Mini Wholemeal Pitta 6pk", 1),
        ],
    },
]


def seed():
    conn = sqlite3.connect(DB_PATH)
    try:
        with conn:
            for table in ("events", "inventory_lots", "order_lines", "orders",
                          "selections", "meal_products", "meals", "products", "users"):
                conn.execute("drop table if exists %s" % table)
            for view in ("leftovers", "leaderboard", "weekly_totals"):
                conn.execute("drop view if exists %s" % view)

            conn.executescript(SCHEMA.read_text())

            conn.executemany(
                "insert into products (name, category, price, shelf_life_days, url, sainsburys_uid) "
                "values (?, ?, ?, ?, ?, ?)",
                PRODUCTS,
            )

            prod_map = {row[1]: row[0] for row in conn.execute("select id, name from products")}

            for meal in MEALS:
                cur = conn.execute(
                    "insert into meals (name, description, tags) values (?, ?, ?)",
                    (meal["name"], meal["description"], json.dumps(meal["tags"])),
                )
                meal_id = cur.lastrowid
                conn.executemany(
                    "insert into meal_products (meal_id, product_id, qty) values (?, ?, ?)",
                    [(meal_id, prod_map[pname], qty) for pname, qty in meal["products"]],
                )

        print("Seeded %d products and %d meals into %s" % (len(PRODUCTS), len(MEALS), DB_PATH))
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
