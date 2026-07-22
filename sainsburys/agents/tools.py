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

SUBMIT_SUGGESTIONS = {
    "name": "submit_suggestions",
    "description": "Finisher: submit a list of meal suggestions for the picker.",
    "input_schema": {
        "type": "object",
        "properties": {
            "meals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "meal_id": {"type": "integer"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["meal_id"],
                },
            },
        },
        "required": ["meals"],
    },
}

SUBMIT_MATCHES = {
    "name": "submit_matches",
    "description": "Finisher: submit personalised rescue matches per user.",
    "input_schema": {
        "type": "object",
        "properties": {
            "matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "user_slack_id": {"type": "string"},
                        "lot_id": {"type": "integer"},
                        "reason": {"type": "string"},
                    },
                    "required": ["user_slack_id", "lot_id", "reason"],
                },
            },
        },
        "required": ["matches"],
    },
}


# ── Tool implementations ───────────────────────────────────────────────────────

def search_products(query: str) -> list:
    raise NotImplementedError


def get_meals() -> list:
    raise NotImplementedError


def get_user_prefs(user_slack_id: str) -> dict:
    raise NotImplementedError


def submit_meal_plan(product_lines: list, half: str, notes: str = "") -> dict:
    # Finisher — the caller reads this back from block.input directly.
    return {"product_lines": product_lines, "half": half, "notes": notes}


def submit_suggestions(meals: list) -> dict:
    return {"meals": meals}


def submit_matches(matches: list) -> dict:
    return {"matches": matches}


IMPLS = {
    "search_products": search_products,
    "get_meals": get_meals,
    "get_user_prefs": get_user_prefs,
    "submit_meal_plan": submit_meal_plan,
    "submit_suggestions": submit_suggestions,
    "submit_matches": submit_matches,
}
