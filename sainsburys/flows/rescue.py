import store
from slack_surface import blocks


def _risk(item):
    """Deterministic expiry-risk score — no LLM here."""
    return (3.0 / (max(item["days_left"], 0) + 0.5)
            + 0.2 * float(item["price"])
            + 0.1 * float(item["qty_left"]))


def board_blocks():
    """Current board blocks, highest expiry risk first — None if fridge is clear."""
    items = sorted(store.leftovers(), key=_risk, reverse=True)
    return blocks.rescue_board_blocks(items) if items else None


def post_board(client, channel):
    """Post the public rescue board, highest expiry risk first."""
    board = board_blocks()
    if not board:
        client.chat_postMessage(channel=channel,
                                text="Fridge is empty — nothing to rescue 🎉")
        return
    client.chat_postMessage(channel=channel,
                            text="🛟 Rescue board — claim it before it's binned",
                            blocks=board)
    # Personalised top-3 DMs (agents/personaliser.py, Track B) plug in here.
