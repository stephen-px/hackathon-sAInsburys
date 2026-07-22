"""
Tool definitions (JSON schemas) and implementations shared across agents.
Each impl is a thin wrapper over store.py.
"""
import store

# ── Tool schemas (pass these to the Anthropic API) ────────────────────────────

SEARCH_PRODUCTS = {
    "name": "search_products",
    "description": "Search the product catalogue by keyword. Returns matching rows.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keyword to search product names/categories"},
        },
        "required": ["query"],
    },
}

GET_MEALS = {
    "name": "get_meals",
    "description": "Return the full meals catalogue with tags and product mappings.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

GET_USER_PREFS = {
    "name": "get_user_prefs",
    "description": "Return dietary constraints and taste profile for a user.",
    "input_schema": {
        "type": "object",
        "properties": {
            "user_slack_id": {"type": "string"},
        },
        "required": ["user_slack_id"],
    },
}

REJECT_REQUEST = {
    "name": "reject_request",
    "description": "Finisher: politely decline a request that is not a food/lunch order "
                   "(non-food items, jokes, impossible asks). Give a short friendly reason.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "One friendly sentence explaining why"},
        },
        "required": ["reason"],
    },
}

SUBMIT_MEAL_PLAN = {
    "name": "submit_meal_plan",
    "description": "Finisher: submit a structured product plan parsed from a freeform request.",
    "input_schema": {
        "type": "object",
        "properties": {
            "product_lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer"},
                        "qty": {"type": "number"},
                    },
                    "required": ["product_id", "qty"],
                },
            },
            "half": {"type": "string", "enum": ["early", "late"]},
            "notes": {"type": "string"},
        },
        "required": ["product_lines", "half"],
    },
}


# ── Tool implementations ───────────────────────────────────────────────────────

def search_products(query: str) -> list:
    return store.search_products_db(query)


def get_meals() -> list:
    return store.get_meals_db()


def get_user_prefs(user_slack_id: str) -> dict:
    return store.get_user_prefs_db(user_slack_id)


def submit_meal_plan(product_lines: list, half: str, notes: str = "") -> dict:
    return {"product_lines": product_lines, "half": half, "notes": notes}


def reject_request(reason: str) -> dict:
    return {"rejected": reason}


IMPLS = {
    "search_products": search_products,
    "get_meals": get_meals,
    "get_user_prefs": get_user_prefs,
    "submit_meal_plan": submit_meal_plan,
    "reject_request": reject_request,
}
