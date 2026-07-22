"""
Seed the product catalogue and demo meals.
Run once after applying schema.sql: python data/seed.py
"""
import os
import psycopg2

DATABASE_URL = os.environ["DATABASE_URL"]

PRODUCTS = [
    # (name, category, price, shelf_life_days)
    ("Sainsbury's Mixed Leaf Salad 100g",              "salad",      1.10,  5),
    ("Sainsbury's Rocket & Spinach Salad 60g",         "salad",      1.00,  5),
    ("Sainsbury's Caesar Salad Kit 400g",              "salad_kit",  2.50,  5),
    ("Sainsbury's Greek Salad Kit 300g",               "salad_kit",  2.20,  5),
    ("Sainsbury's Tabbouleh 300g",                     "salad",      2.00,  5),
    ("Sainsbury's Cherry Tomatoes 250g",               "salad",      1.10,  5),
    ("Sainsbury's Cucumber",                           "salad",      0.60,  7),
    ("Sainsbury's Cooked Chicken Breast 125g",         "protein",    2.20,  4),
    ("Sainsbury's Chicken Tikka Pieces 150g",          "protein",    2.50,  3),
    ("Sainsbury's Prawn Cocktail 150g",                "protein",    2.80,  3),
    ("Sainsbury's Smoked Salmon 100g",                 "protein",    3.50,  5),
    ("Sainsbury's Honey Roast Salmon Flakes 120g",     "protein",    3.00,  4),
    ("Sainsbury's Tuna in Spring Water 145g",          "protein",    1.25, 730),
    ("Sainsbury's Mature Cheddar Slices 10pk",         "dairy",      2.00, 14),
    ("Sainsbury's Feta Cheese 200g",                   "dairy",      2.50, 14),
    ("Sainsbury's Hummus 200g",                        "dip",        1.35, 14),
    ("Sainsbury's Guacamole 150g",                     "dip",        1.85,  7),
    ("Sainsbury's Reduced Fat Mayo 400g",              "condiment",  1.65, 60),
    ("Sainsbury's Soft Flour Tortilla Wraps 8pk",      "carb",       1.35,  7),
    ("Sainsbury's Plain Bagels 5pk",                   "carb",       1.50,  5),
    ("Sainsbury's Mini Wholemeal Pitta 6pk",           "carb",       1.20,  5),
    ("Sainsbury's Sliced White Bread 800g",            "carb",       1.30,  5),
    ("Sainsbury's Avocado (each)",                     "fruit",      0.80,  3),
    ("Sainsbury's Banana 5pk",                         "fruit",      0.90,  5),
    ("Sainsbury's Easy Peeler Oranges 4pk",            "fruit",      1.50,  7),
    ("Sainsbury's Jazz Apple 4pk",                     "fruit",      1.20, 14),
    ("Sainsbury's Seedless Grapes 500g",               "fruit",      2.00,  7),
    ("Sainsbury's Sparkling Water 6x500ml",            "drink",      2.50, 365),
    ("Sainsbury's Ready Salted Crisps 6pk",            "snack",      1.75, 180),
    ("Sainsbury's Trail Mix 200g",                     "snack",      2.00, 90),
]

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
            ("Sainsbury's Smoked Salmon 100g",   1),
            ("Sainsbury's Guacamole 150g",        1),
            ("Sainsbury's Plain Bagels 5pk",      1),
        ],
    },
    {
        "name": "Salmon & Tabbouleh Bowl",
        "description": "Honey roast salmon flakes over tabbouleh",
        "tags": ["seafood", "salad", "gluten-free", "no-meat"],
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
            ("Sainsbury's Chicken Tikka Pieces 150g",      1),
            ("Sainsbury's Mixed Leaf Salad 100g",          1),
            ("Sainsbury's Soft Flour Tortilla Wraps 8pk",  1),
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
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "TRUNCATE meal_products, meals, products, users "
                    "RESTART IDENTITY CASCADE"
                )

                cur.executemany(
                    "INSERT INTO products (name, category, price, shelf_life_days) "
                    "VALUES (%s, %s, %s, %s)",
                    PRODUCTS,
                )

                cur.execute("SELECT id, name FROM products")
                prod_map = {row[1]: row[0] for row in cur.fetchall()}

                for meal in MEALS:
                    cur.execute(
                        "INSERT INTO meals (name, description, tags) VALUES (%s, %s, %s) RETURNING id",
                        (meal["name"], meal["description"], meal["tags"]),
                    )
                    meal_id = cur.fetchone()[0]
                    cur.executemany(
                        "INSERT INTO meal_products (meal_id, product_id, qty) VALUES (%s, %s, %s)",
                        [(meal_id, prod_map[pname], qty) for pname, qty in meal["products"]],
                    )

        print(f"Seeded {len(PRODUCTS)} products and {len(MEALS)} meals.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
