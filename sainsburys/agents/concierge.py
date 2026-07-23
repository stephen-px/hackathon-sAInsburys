"""
Basket Agent — unified lunch concierge: parses concrete orders, suggests when
the request is vague or empty, refines on feedback. One agent, one flow.
"""
import json
from pathlib import Path
from agents.loop import run_agent
from agents.tools import SEARCH_PRODUCTS, GET_MEALS, GET_USER_PREFS, SUBMIT_MEAL_PLAN, REJECT_REQUEST, IMPLS

SYSTEM = (Path(__file__).parent / "prompts" / "concierge.md").read_text()
TOOLS = [SEARCH_PRODUCTS, GET_MEALS, GET_USER_PREFS, SUBMIT_MEAL_PLAN, REJECT_REQUEST]
FINISHERS = {"submit_meal_plan", "reject_request"}


def plan(user_slack_id, text, half, previous=None, feedback=None):
    """
    Turn a request (or lack of one) into a proposed plan.
    Returns {product_lines: [{product_id, qty}], half, notes}
    or {rejected: reason}.
    """
    parts = [f"User: {user_slack_id}", f"Delivery half: {half}"]
    text = (text or "").strip()
    parts.append("Request: %s" % (text if text else "(none — they want you to pick)"))
    if previous:
        parts.append("REFINEMENT — previous plan (product lines): %s"
                     % json.dumps(previous.get("product_lines", [])))
        if previous.get("notes"):
            parts.append("Previous notes: %s" % previous["notes"])
        parts.append("User feedback on it: %s" % (feedback or ""))
    resp = run_agent(SYSTEM, "\n".join(parts), TOOLS, IMPLS, max_turns=8, finisher=FINISHERS)
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            if block.name == "submit_meal_plan":
                return block.input
            if block.name == "reject_request":
                return {"rejected": block.input.get("reason", "That's not something I can order.")}
    raise RuntimeError(f"concierge did not call a finisher tool: {resp}")
