import store
from flows.basket import _current_week
from slack_surface import blocks


def send_checkin_dms(client):
    """DM each user their ordered items for the week + Ate/Some/None buttons.
    Answers shrink the rescue board and the answerer's waste score — items stay
    on the board either way (no gate)."""
    week = _current_week()
    sent = 0
    for user in store.users_with_selections(week):
        items = store.open_items_for(user, week)
        if not items:
            continue
        dm = client.conversations_open(users=user)
        client.chat_postMessage(channel=dm["channel"]["id"],
                                text="Friday check-in — how did you get on?",
                                blocks=blocks.checkin_blocks(items),
                                unfurl_links=False, unfurl_media=False)
        sent += 1
    return sent


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
                            blocks=board,
                            unfurl_links=False, unfurl_media=False)
    # Personalised top-3 DMs (agents/personaliser.py, Track B) plug in here.
