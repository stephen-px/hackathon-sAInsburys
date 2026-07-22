# Block Kit builders — TODO
def meal_picker_blocks(suggestions): raise NotImplementedError


def basket_blocks(order):
    """Block Kit message for one draft basket order with an Approve button."""
    lines = order.get("lines", [])
    total = sum(l["qty"] * l["unit_price"] for l in lines)
    delivery = order["delivery_date"]
    half_label = "Mon" if "01" in str(delivery)[-5:] or int(str(delivery)[8:10]) % 7 in (0, 1) else "delivery"
    items_text = "\n".join(
        "• %gx *%s* — £%.2f" % (l["qty"], l["name"], l["qty"] * l["unit_price"])
        for l in lines
    ) or "_No items_"
    return [
        {"type": "header", "text": {"type": "plain_text", "text": "🛒 Basket — %s" % delivery}},
        {"type": "section", "text": {"type": "mrkdwn", "text": items_text}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "*Total: £%.2f*" % total}]},
        {"type": "actions", "elements": [
            {"type": "button", "style": "primary",
             "text": {"type": "plain_text", "text": "✅ Approve order"},
             "action_id": "approve_order", "value": str(order["id"])},
        ]},
    ]


def rescue_board_blocks(lots):
    """Block Kit message for the public rescue board — one Claim button per lot."""
    blks = [
        {"type": "header", "text": {"type": "plain_text", "text": "🛟 Rescue Board — save it from the bin!"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": "Tap *Claim* on anything you'll eat. Every claim ticks the counter. 💚"}]},
        {"type": "divider"},
    ]
    for lot in lots:
        days = lot.get("days_left", 0)
        if days <= 0:
            urgency = "🔴 *Expires today!*"
        elif days == 1:
            urgency = "⚠️ 1 day left"
        else:
            urgency = "🟡 %d days left" % days
        blks.append({
            "type": "section",
            "text": {"type": "mrkdwn",
                     "text": "*%s*  %s   £%.2f  ×%g remaining" % (
                         lot["name"], urgency, lot["price"], lot["qty_remaining"])},
            "accessory": {
                "type": "button", "style": "primary",
                "text": {"type": "plain_text", "text": "Claim 🙌"},
                "action_id": "claim_lot", "value": str(lot["id"]),
            },
        })
    return blks


def digest_blocks(digest):
    """Weekly waste sweep summary."""
    n = digest.get("wasted_items", 0)
    v = digest.get("wasted_value", 0.0)
    msg = ("🗑️ *%d item%s swept as waste — £%.2f lost.*  "
           "Less next week: order only what you'll eat." % (n, "s" if n != 1 else "", v))
    return [{"type": "section", "text": {"type": "mrkdwn", "text": msg}}]


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
