"""
Basket Agent — Step 1: suggest 5 meals for the week picker.
"""
from pathlib import Path
from agents.loop import run_agent
from agents.tools import GET_MEALS, GET_USER_PREFS, SUBMIT_SUGGESTIONS, IMPLS

SYSTEM = (Path(__file__).parent / "prompts" / "suggester.md").read_text()
TOOLS = [GET_MEALS, GET_USER_PREFS, SUBMIT_SUGGESTIONS]


def suggest(user_slack_ids: list, last_two_weeks_meal_ids: list) -> list:
    """Return up to 5 meal dicts: [{meal_id, rationale}, ...]"""
    user_msg = (
        f"Users: {user_slack_ids}\n"
        f"Meals served in the last two weeks (avoid repeats): {last_two_weeks_meal_ids}"
    )
    resp = run_agent(SYSTEM, user_msg, TOOLS, IMPLS)
    # The finisher tool wrote structured output; find it in the last tool_use block.
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_suggestions":
            return block.input["meals"]
    # Fallback: agent answered in text (shouldn't happen with a well-written prompt)
    raise RuntimeError(f"suggester did not call submit_suggestions: {resp}")
