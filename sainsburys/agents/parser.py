"""
Basket Agent — Step 3: parse freeform meal requests into product lines.
"""
from pathlib import Path
from agents.loop import run_agent
from agents.tools import SEARCH_PRODUCTS, GET_MEALS, GET_USER_PREFS, SUBMIT_MEAL_PLAN, IMPLS

SYSTEM = (Path(__file__).parent / "prompts" / "parser.md").read_text()
TOOLS = [SEARCH_PRODUCTS, GET_MEALS, GET_USER_PREFS, SUBMIT_MEAL_PLAN]


def parse(user_slack_id: str, freeform: str, half: str) -> dict:
    """
    Parse a freeform lunch request for a user.
    Returns {product_lines: [{product_id, qty}], half, notes}.
    """
    user_msg = f"User: {user_slack_id}\nDelivery half: {half}\nRequest: {freeform}"
    resp = run_agent(SYSTEM, user_msg, TOOLS, IMPLS, max_turns=6)
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_meal_plan":
            return block.input
    raise RuntimeError(f"parser did not call submit_meal_plan: {resp}")
