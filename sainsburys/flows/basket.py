import store
from agents import parser as parser_agent
from datetime import date, timedelta


def _current_week():
    today = date.today()
    return today - timedelta(days=today.weekday())


def _format_lines(product_lines, products):
    lines = []
    for line in product_lines:
        product = products.get(line["product_id"], {})
        name = product.get("name") or "Product %s" % line["product_id"]
        cost = float(product.get("price") or 0) * float(line["qty"])
        lines.append("• {qty}x *{name}* — £{cost:.2f}".format(qty=line["qty"], name=name, cost=cost))
    return "\n".join(lines)


def handle_order_submit(body, client):
    user_id = body["user"]["id"]
    user_name = body["user"].get("username", body["user"].get("name", user_id))
    values = body["view"]["state"]["values"]
    order_text = values["order_text"]["text"]["value"]
    half = values["order_half"]["half"]["selected_option"]["value"]
    week = _current_week()

    store.ensure_user(user_id, user_name)

    dm = client.conversations_open(users=user_id)
    dm_channel = dm["channel"]["id"]
    client.chat_postMessage(
        channel=dm_channel,
        text=":mag: Parsing your order... one sec!",
    )

    print("[order] user=%s half=%s text=%r" % (user_id, half, order_text), flush=True)

    try:
        result = parser_agent.parse(user_id, order_text, half)
        row = store.record_selection(user_id, week, half, freeform=order_text, parsed=result)
        print("[order] recorded selection id=%s lines=%s" % (row["id"], result.get("product_lines")), flush=True)

        product_ids = [line["product_id"] for line in result.get("product_lines", [])]
        products = {p["id"]: p for p in store.get_products_by_ids(product_ids)}
        lines_text = _format_lines(result.get("product_lines", []), products)
        notes = "\n_Note: %s_" % result["notes"] if result.get("notes") else ""

        client.chat_postMessage(
            channel=dm_channel,
            text=(
                ":white_check_mark: *Order logged for %s week!*\n"
                "%s%s\n\n"
                '_Your request: "%s"_' % (half, lines_text, notes, order_text)
            ),
        )

    except Exception as e:
        store.record_selection(user_id, week, half, freeform=order_text)
        client.chat_postMessage(
            channel=dm_channel,
            text=(
                ":warning: Couldn't parse your order automatically, but I saved your request:\n"
                "> %s\n"
                "_Error: %s: %s_" % (order_text, type(e).__name__, e)
            ),
        )


# ── /demo-deliver (Track A) ────────────────────────────────────────────────────

def simulate_delivery(client, channel, order_ids=None):
    """
    Create fridge lots. Delivers explicit ids, else the week's approved orders.
    Demo shortcut until /demo-aggregate lands: with nothing approved, build
    baskets from this week's selections and deliver them directly (says so).
    """
    week = _current_week()
    shortcut = False
    if order_ids:
        ids = order_ids
    else:
        ids = [o["id"] for o in store.approved_orders(week)]
        if not ids:
            drafts = store.build_baskets(week)
            if not drafts:
                client.chat_postMessage(channel=channel,
                                        text="Nothing to deliver — no selections this week yet.")
                return
            ids = [store.approve_order(o["id"])["id"] for o in drafts]
            shortcut = True

    lots = []
    for oid in ids:
        lots.extend(store.deliver_order(oid))

    note = ("\n_(demo shortcut: no approved baskets, so this week's selections were "
            "built and delivered directly — the Approve step arrives with /demo-aggregate)_"
            if shortcut else "")
    client.chat_postMessage(
        channel=channel,
        text="📦 Delivery logged — %d lots now in the fridge.%s" % (len(lots), note))
