import store
from flows.basket import _current_week
from slack_surface import blocks


def send_checkin_dms(client):
    """DM each user their ordered items for the week + Ate/Some/None buttons."""
    week = _current_week()
    sent = 0
    for user in store.users_with_selections(week):
        items = store.open_items_for(user, week)
        if not items:
            continue
        dm = client.conversations_open(users=user)
        client.chat_postMessage(channel=dm["channel"]["id"],
                                text="Friday check-in — how did you get on?",
                                blocks=blocks.checkin_blocks(items))
        sent += 1
    return sent


# TODO
def post_board(client, channel): raise NotImplementedError
def sweep_and_digest(client, channel): raise NotImplementedError
