# Block Kit builders — TODO
def meal_picker_blocks(suggestions): raise NotImplementedError
def rescue_board_blocks(lots): raise NotImplementedError
def digest_blocks(digest): raise NotImplementedError
def basket_blocks(order): raise NotImplementedError


def checkin_blocks(items):
    """One section + Ate/Some/None button row per ordered item ({product_id, name, qty})."""
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "🍽️ Friday check-in"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": "How did you get on with this week's food? One tap per item."}]},
        {"type": "divider"},
    ]
    for item in items:
        product_id = str(item["product_id"])
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*%s*" % item["name"]}})
        blocks.append({"type": "actions", "elements": [
            {"type": "button", "style": "primary", "text": {"type": "plain_text", "text": "Ate it"},
             "action_id": "checkin_ate", "value": product_id},
            {"type": "button", "text": {"type": "plain_text", "text": "Some left"},
             "action_id": "checkin_some", "value": product_id},
            {"type": "button", "style": "danger", "text": {"type": "plain_text", "text": "Didn't touch"},
             "action_id": "checkin_none", "value": product_id},
        ]})
    return blocks
