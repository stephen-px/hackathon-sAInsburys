"""
Rescue Board Agent — Step 3: personalise rescue recommendations per user.
"""
from pathlib import Path
from agents.loop import run_agent
from agents.tools import SUBMIT_MATCHES, IMPLS
import store

SYSTEM = (Path(__file__).parent / "prompts" / "personaliser.md").read_text()
TOOLS = [SUBMIT_MATCHES]


def personalise(in_office_users: list) -> dict:
    """
    Given users who are in the office, return matches:
    {user_slack_id: [{lot_id, reason}, ...]}
    """
    lots = store.leftovers()
    prefs = {u: store.get_user_prefs(u) for u in in_office_users}  # type: ignore

    user_msg = (
        f"Leftovers (sorted by expiry):\n{lots}\n\n"
        f"In-office users and taste profiles:\n{prefs}"
    )
    resp = run_agent(SYSTEM, user_msg, TOOLS, IMPLS, max_turns=4)
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_matches":
            matches = block.input["matches"]
            result = {}
            for m in matches:
                result.setdefault(m["user_slack_id"], []).append(
                    {"lot_id": m["lot_id"], "reason": m["reason"]}
                )
            return result
    raise RuntimeError(f"personaliser did not call submit_matches: {resp}")
