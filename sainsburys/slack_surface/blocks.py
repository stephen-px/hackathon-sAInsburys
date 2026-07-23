# Block Kit builders
def meal_picker_blocks(suggestions): raise NotImplementedError  # TODO


def digest_blocks(digest):
    """Weekly waste sweep summary + wall of shame, posted by /reset."""
    n = digest.get("wasted_items", 0)
    v = digest.get("wasted_value", 0.0)
    out = [
        {"type": "header", "text": {"type": "plain_text", "text": "🗑️ Weekly sweep"}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": "*%d item%s went in the bin — £%.2f wasted.*" % (n, "s" if n != 1 else "", v)
                    if n else "*Nothing wasted — clean fridge!* 🎉"}},
    ]
    wasters = digest.get("by_user") or []
    if wasters:
        medals = ["🥇", "🥈", "🥉"]
        lines = "\n".join(
            "%s <@%s> — £%.2f binned" % (medals[i] if i < 3 else "·", w["slack_id"], w["wasted"])
            for i, w in enumerate(wasters[:5])
        )
        out.append({"type": "section", "text": {"type": "mrkdwn",
                    "text": "*Biggest wasters* (points deducted):\n%s" % lines}})
    out.append({"type": "context", "elements": [{"type": "mrkdwn",
                "text": "Orders wiped — fresh week starts now. Wasted £ counts against your leaderboard score."}]})
    return out


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


def suggestion_blocks(selection_id, lines_text, notes, mood, ordered=False):
    """A lunch plan DM. Proposed: Order it / Change something. Ordered: stays
    amendable — a Change button remains and edits apply straight away."""
    sid = str(selection_id)
    header = ":white_check_mark: *Your order*" if ordered else ":bulb: *How about this?*"
    if notes:
        header += "\n_%s_" % notes
    request = (mood or "").strip()
    context = ("You asked for: “%s”" % request) if request and request != "(surprise me)" \
        else "Surprise pick — no brief given"
    if ordered:
        context += "  ·  ✅ Ordered — changes apply straight away"
        buttons = [
            {"type": "button",
             "text": {"type": "plain_text", "text": "Change something 🔄"},
             "action_id": "suggestion_refine", "value": sid},
        ]
    else:
        buttons = [
            {"type": "button", "style": "primary",
             "text": {"type": "plain_text", "text": "Order it ✅"},
             "action_id": "suggestion_accept", "value": sid},
            {"type": "button",
             "text": {"type": "plain_text", "text": "Change something 🔄"},
             "action_id": "suggestion_refine", "value": sid},
        ]
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "section", "text": {"type": "mrkdwn", "text": lines_text}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": context}]},
        {"type": "actions", "elements": buttons},
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

