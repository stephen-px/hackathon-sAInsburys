"""
Basket Agent — open suggestions: propose a lunch plan, refine on feedback.
"""
import json
from pathlib import Path
from agents.loop import run_agent
from agents.tools import SEARCH_PRODUCTS, GET_MEALS, GET_USER_PREFS, SUBMIT_MEAL_PLAN, REJECT_REQUEST, IMPLS

SYSTEM = (Path(__file__).parent / "prompts" / "suggester.md").read_text()
TOOLS = [SEARCH_PRODUCTS, GET_MEALS, GET_USER_PREFS, SUBMIT_MEAL_PLAN, REJECT_REQUEST]
FINISHERS = {"submit_meal_plan", "reject_request"}


def suggest(user_slack_id, mood, half, previous=None, feedback=None):
    """
    Propose (or refine) a lunch plan.
    Returns {product_lines: [{product_id, qty}], half, notes}
    or {rejected: reason}.
    """
    parts = [f"User: {user_slack_id}", f"Delivery half: {half}"]
    parts.append("Mood/preferences: %s" % (mood.strip() if mood and mood.strip()
                                           else "none given — surprise them"))
    if previous:
        parts.append("REFINEMENT — previous suggestion (product lines): %s"
                     % json.dumps(previous.get("product_lines", [])))
        parts.append("Previous pitch: %s" % previous.get("notes", ""))
        parts.append("User feedback on it: %s" % (feedback or ""))
    resp = run_agent(SYSTEM, "\n".join(parts), TOOLS, IMPLS, max_turns=8, finisher=FINISHERS)
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            if block.name == "submit_meal_plan":
                return block.input
            if block.name == "reject_request":
                return {"rejected": block.input.get("reason", "That's not something I can help with.")}
    raise RuntimeError(f"suggester did not call a finisher tool: {resp}")
