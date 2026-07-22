"""
Seed the product catalogue and demo meals into SQLite.
Safe to re-run: drops all tables and recreates from schema_sqlite.sql.

    python data/seed.py
"""
import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "lunch.db"
SCHEMA = DATA_DIR / "schema_sqlite.sql"

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
    # ── From real order receipt 1327783937 (22 Jul 2026); unit price = line total / qty ──
    # Ready meals (microwave)
    ("Wasabi Chicken Katsu Curry with Rice 450g",                        "ready_meal", 5.00, 3),
    ("Wasabi Sweet Chilli Chicken with Rice 450g",                       "ready_meal", 5.00, 3),
    ("Sainsbury's Beef Lasagne Ready Meal for 1 400g",                   "ready_meal", 3.19, 4),
    ("Sainsbury's Chicken Jambalaya Ready Meal for 1 400g",              "ready_meal", 3.00, 4),
    ("Sainsbury's Indian Chicken Tikka Biryani Ready Meal for 1 400g",   "ready_meal", 3.00, 4),
    ("Sainsbury's Paneer Tikka Masala with Cumin Rice 400g",             "ready_meal", 3.00, 4),
    ("Sainsbury's Indian Tadka Daal Side for 2 300g",                    "ready_meal", 2.60, 4),
    ("The Gym Kitchen Thai Green Chicken Curry 400g",                    "ready_meal", 4.00, 4),
    ("Sainsbury's Beef Brisket with Red Wine Jus 385g",                  "ready_meal", 4.20, 4),
    ("Sainsbury's Creamy Sausage Ragu 375g",                             "ready_meal", 4.00, 4),
    ("Sainsbury's Mushroom Pappardelle 400g",                            "ready_meal", 4.00, 4),
    # Sandwiches
    ("Sainsbury's Red Leicester Ploughmans Sandwich",                    "sandwich",   3.10, 2),
    ("Sainsbury's Smoked Salmon & Cream Cheese Oatmeal Sandwich",        "sandwich",   3.50, 2),
    ("Sainsbury's Steak & Caramelised Red Onion Sandwich",               "sandwich",   4.50, 2),
    # Salads & bowls
    ("Sainsbury's Beetroot & Feta Salad 175g",                           "salad",      2.75, 3),
    ("Sainsbury's Greek Inspired Whipped Feta Salad 220g",               "salad",      2.67, 3),
    ("Sainsbury's Bistro Salad 150g",                                    "salad",      1.35, 3),
    ("Sainsbury's Greek Style Salad Bowl 220g",                          "salad",      2.75, 3),
    ("Sainsbury's Pasta, Spinach & Pinenut Salad 200g",                  "salad",      1.60, 3),
    ("Sainsbury's Feta, Tomato & Basil Pasta 225g",                      "salad",      3.00, 3),
    ("Sainsbury's Pesto & Parmesan Pasta 185g",                          "salad",      2.67, 3),
    ("Sainsbury's Giant Cous Cous & Feta Salad 220g",                    "salad",      2.66, 3),
    ("Sainsbury's Sweet & Crispy Salad Bowl 175g",                       "salad",      1.45, 3),
    ("Sainsbury's Sweet Leaf Salad 250g",                                "salad",      0.78, 4),
    ("Sainsbury's Wild Rocket 60g",                                      "salad",      1.00, 5),
    ("Sainsbury's Tabbouleh with Herb Roasted Garlic & Lemon 200g",      "salad",      2.67, 4),
    ("Sainsbury's Vittoria Cherry Vine Tomatoes 250g",                   "salad",      2.35, 5),
    ("Sainsbury's British Prepared Mini Carrots 240g",                   "salad",      1.00, 7),
    # Protein
    ("Sainsbury's Free Range Egg Pot 90g",                               "protein",    1.40, 3),
    ("Sainsbury's Cajun Chicken Grills Ready to Eat 180g",               "protein",    3.25, 4),
    ("Sainsbury's Tikka Cooked Chicken Mini Fillets 170g",               "protein",    3.25, 4),
    ("Sainsbury's Roast Chicken Cocktail Sausages 198g",                 "protein",    2.67, 4),
    ("Sainsbury's Hickory Wood Smoked Salmon 100g",                      "protein",    4.95, 5),
    ("Sainsbury's SO Organic Smoked Salmon 100g",                        "protein",    5.95, 5),
    ("Sainsbury's Lemon & Herb Steamed Salmon Portions x2 180g",         "protein",    5.95, 4),
    ("Sainsbury's Sweet Chilli Salmon Portions x2 180g",                 "protein",    4.95, 4),
    ("Sainsbury's Pil Pil King Prawns 135g",                             "protein",    2.77, 3),
    ("Sainsbury's King Prawns, Sunblush Tomatoes & Pesto 150g",          "protein",    2.77, 3),
    ("Sainsbury's Italian Bresaola x15 80g",                             "protein",    2.46, 7),
    ("Sainsbury's Sweet Potato Falafels 144g",                           "protein",    2.66, 4),
    ("Sainsbury's Falafels Summer Edition 144g",                         "protein",    2.67, 4),
    # Plant-based
    ("This Isn't Chicken Plant Based Pieces 170g",                       "plant_based", 3.50, 5),
    ("This Isn't Pork Salami Slices 70g",                                "plant_based", 2.95, 7),
    ("La Vie Plant Based Smoked Ham 100g",                               "plant_based", 3.00, 7),
    # Grains (ambient pouches)
    ("Merchant Gourmet Persian Style Rice & Lentils 250g",               "grains",     1.50, 180),
    ("Merchant Gourmet 3 Bean & Lentil Chilli 280g",                     "grains",     2.50, 180),
    ("Merchant Gourmet Beluga Lentils 250g",                             "grains",     1.50, 180),
    ("Merchant Gourmet Puy & French Green Lentils 250g",                 "grains",     1.50, 180),
    # Dairy
    ("Sainsbury's Italian Burrata 150g",                                 "dairy",      3.20, 7),
    ("Sainsbury's Mozzarella Cheese Pearls 125g",                        "dairy",      1.90, 7),
    ("Galbani Italian Mozzarella 125g",                                  "dairy",      1.95, 7),
    ("Arla Cottage Cheese 300g",                                         "dairy",      1.90, 10),
    ("Piatnica High Protein Cottage Cheese 200g",                        "dairy",      1.25, 10),
    # Fruit
    ("Sainsbury's Mango 120g",                                           "fruit",      1.15, 3),
    ("Sainsbury's Strawberries 400g",                                    "fruit",      1.95, 4),
    ("Sainsbury's Blueberries 300g",                                     "fruit",      2.75, 7),
    ("Sainsbury's Raspberries 250g",                                     "fruit",      2.50, 4),
    ("Sainsbury's Pink Lady Apples 6pk",                                 "fruit",      2.90, 14),
    ("Sainsbury's Red Seedless Grapes 500g",                             "fruit",      2.20, 7),
    ("Sainsbury's Fairtrade Bananas x8",                                 "fruit",      1.39, 5),
    ("Sainsbury's Medjool Dates 200g",                                   "fruit",      2.60, 90),
    # Snacks
    ("Sainsbury's Whole Almonds 300g",                                   "snack",      3.50, 90),
    ("Sainsbury's Walnut Pieces 200g",                                   "snack",      2.35, 90),
    ("Nakd Berry Delight Fruit & Nut Bars 4x35g",                        "snack",      2.25, 180),
    ("Eat Real Veggie Straws 5x16g",                                     "snack",      1.75, 180),
    ("Sun Bites Sour Cream & Black Pepper 6x25g",                        "snack",      2.20, 180),
    ("Hula Hoops Variety Crisps 12x24g",                                 "snack",      3.50, 180),
    # Bakery
    ("Higgidy Cheddar & Caramelised Onion Chutney Rolls 160g",           "bakery",     3.30, 4),
    ("Higgidy Hoisin Pulled Mushroom & Spring Onion Rolls 160g",         "bakery",     3.50, 4),
    ("Jason's Sourdough The Great White Bread 450g",                     "carb",       2.20, 4),
    ("Warburtons Gluten Free Brown Soft Pittas x4",                      "carb",       2.50, 5),
    # Dips & condiments
    ("Yarden Houmous Extra 250g",                                        "dip",        2.65, 10),
    ("Sainsbury's SO Organic Pitted Kalamata Olives 295g",               "condiment",  3.05, 30),
    ("itsu Crispy Chilli Oil 100g",                                      "condiment",  2.00, 365),
    # Drinks
    ("Oatly Oat Drink Barista Edition 1L",                               "drink",      2.20, 180),
    ("Vita Coco Coconut Water 1L",                                       "drink",      4.00, 180),
    ("Sainsbury's Semi Skimmed Milk 3.4L (6 pint)",                      "drink",      2.40, 7),
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
                "insert into products (name, category, price, shelf_life_days) values (?, ?, ?, ?)",
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
