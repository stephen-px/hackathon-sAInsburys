# Block Kit builders — TODO
def meal_picker_blocks(suggestions): raise NotImplementedError
def basket_blocks(order):
    """Block Kit message for one draft basket order with an Approve button."""
    lines = order.get("lines", [])
    total = sum(l["qty"] * l["unit_price"] for l in lines)
    delivery = order["delivery_date"]
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


def digest_blocks(digest):
    """Weekly waste sweep summary."""
    n = digest.get("wasted_items", 0)
    v = digest.get("wasted_value", 0.0)
    msg = ("🗑️ *%d item%s swept as waste — £%.2f lost.*  "
           "Less next week: order only what you'll eat." % (n, "s" if n != 1 else "", v))
    return [{"type": "section", "text": {"type": "mrkdwn", "text": msg}}]


def order_confirmation_blocks(selection_id, half, lines_text, notes, order_text):
    """Parsed order + Looks right / Fix it buttons (the hallucination backstop)."""
    body = ":white_check_mark: *Order logged for %s week!*\n%s" % (half, lines_text)
    if notes:
        body += "\n_Note: %s_" % notes
    sid = str(selection_id)
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": body}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": "Your request: “%s”" % order_text}]},
        {"type": "actions", "elements": [
            {"type": "button", "style": "primary",
             "text": {"type": "plain_text", "text": "Looks right ✅"},
             "action_id": "order_confirm", "value": sid},
            {"type": "button",
             "text": {"type": "plain_text", "text": "Fix it ✏️"},
             "action_id": "order_fix", "value": sid},
        ]},
    ]


def order_failure_blocks(selection_id, order_text, err):
    """Parse failed: raw request saved, offer a one-tap retry."""
    return [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": ":warning: Couldn't parse your order automatically, but I saved it:\n> %s" % order_text}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": err}]},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Retry 🔁"},
             "action_id": "order_retry", "value": str(selection_id)},
        ]},
    ]


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
        # value carries "product_id:qty_ordered" so the tap logs the right amount
        value = "%s:%g" % (item["product_id"], item["qty"])
        label = "*%s*" % item["name"]
        if item["qty"] > 1:
            label += "  ×%g" % item["qty"]
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": label}})
        blocks.append({"type": "actions", "elements": [
            {"type": "button", "style": "primary", "text": {"type": "plain_text", "text": "Ate it"},
             "action_id": "checkin_ate", "value": value},
            {"type": "button", "text": {"type": "plain_text", "text": "Some left"},
             "action_id": "checkin_some", "value": value},
            {"type": "button", "style": "danger", "text": {"type": "plain_text", "text": "Didn't touch"},
             "action_id": "checkin_none", "value": value},
        ]})
    return blocks
