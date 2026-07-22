# Block Kit builders — TODO
def meal_picker_blocks(suggestions): raise NotImplementedError
def digest_blocks(digest): raise NotImplementedError
def basket_blocks(order): raise NotImplementedError


def rescue_board_blocks(items):
    """Risk-sorted leftovers ({product_id, name, price, qty_left, days_left}), one Claim button each."""
    blocks = [
        {"type": "header", "text": {"type": "plain_text",
            "text": "🛟 Rescue board — claim it before it's binned"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": "One tap = it's yours. Every claim counts as money saved from the bin."}]},
        {"type": "divider"},
    ]
    for item in items:
        days = item["days_left"]
        urgency = ("🔴 expires *today*" if days <= 0
                   else "🟠 *%d day%s* left" % (days, "" if days == 1 else "s") if days <= 2
                   else "🟢 %d days left" % days)
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*%s*\n£%.2f · %g left · %s" % (
                item["name"], float(item["price"]), item["qty_left"], urgency)},
            "accessory": {"type": "button", "style": "primary",
                          "text": {"type": "plain_text", "text": "Claim"},
                          "action_id": "claim", "value": str(item["product_id"])},
        })
    return blocks


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
