import json

import store
from agents import concierge
from datetime import date, timedelta
from slack_surface import blocks


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


def _send_plan(client, dm_channel, selection_id, result, request_text):
    """DM the proposed plan with Order it / Change something buttons."""
    product_ids = [line["product_id"] for line in result.get("product_lines", [])]
    products = {p["id"]: p for p in store.get_products_by_ids(product_ids)}
    lines_text = _format_lines(result.get("product_lines", []), products)
    client.chat_postMessage(
        channel=dm_channel,
        text="Proposed lunch: %s" % (result.get("notes") or lines_text),
        blocks=blocks.suggestion_blocks(selection_id, lines_text,
                                        result.get("notes") or "", request_text),
    )


def handle_order_submit(body, client):
    """
    One flow for everything: concrete requests get parsed, vague or empty ones
    get a suggestion — either way the user reviews a proposal and taps
    Order it / Change something.
    """
    user_id = body["user"]["id"]
    user_name = body["user"].get("username", body["user"].get("name", user_id))
    values = body["view"]["state"]["values"]
    order_text = (values["order_text"]["text"].get("value") or "").strip()
    half = values["order_half"]["half"]["selected_option"]["value"]
    week = _current_week()

    store.ensure_user(user_id, user_name)

    dm = client.conversations_open(users=user_id)
    dm_channel = dm["channel"]["id"]
    client.chat_postMessage(
        channel=dm_channel,
        text=":bulb: On it — putting your lunch together..." if not order_text
             else ":mag: Parsing your order... one sec!",
    )

    print("[plan] user=%s half=%s text=%r" % (user_id, half, order_text), flush=True)

    try:
        result = concierge.plan(user_id, order_text, half)

        if result.get("rejected"):
            print("[plan] rejected: %s" % result["rejected"], flush=True)
            client.chat_postMessage(
                channel=dm_channel,
                text=":no_good: %s\n_Your request: \"%s\"_" % (result["rejected"], order_text),
            )
            return

        row = store.record_selection(user_id, week, half,
                                     freeform=order_text or "(surprise me)",
                                     parsed=result, status="proposed")
        print("[plan] proposed selection id=%s lines=%s" % (row["id"], result.get("product_lines")), flush=True)
        _send_plan(client, dm_channel, row["id"], result, order_text)

    except Exception as e:
        row = store.record_selection(user_id, week, half, freeform=order_text)
        print("[plan] failed (%s), saved raw as id=%s" % (e, row["id"]), flush=True)
        client.chat_postMessage(
            channel=dm_channel,
            text="Couldn't put a plan together — saved the raw request.",
            blocks=blocks.order_failure_blocks(row["id"], order_text, "%s: %s" % (type(e).__name__, e)),
        )


def handle_refine_submit(body, client):
    """User told us what to change about a proposed plan — re-run with context."""
    selection_id = int(body["view"]["private_metadata"])
    feedback = body["view"]["state"]["values"]["refine_text"]["feedback"]["value"]
    user_id = body["user"]["id"]

    dm = client.conversations_open(users=user_id)
    dm_channel = dm["channel"]["id"]

    sel = store.get_selection(selection_id)
    if not sel or sel["status"] != "proposed":
        client.chat_postMessage(channel=dm_channel,
                                text="🤔 That plan is gone — run /order again.")
        return

    client.chat_postMessage(channel=dm_channel, text=":bulb: Reworking it...")
    print("[plan] refine id=%s feedback=%r" % (selection_id, feedback), flush=True)
    try:
        previous = json.loads(sel["parsed"]) if sel["parsed"] else None
        result = concierge.plan(user_id, sel["freeform"], sel["half"],
                                previous=previous, feedback=feedback)
        if result.get("rejected"):
            client.chat_postMessage(channel=dm_channel, text=":no_good: %s" % result["rejected"])
            return
        store.update_selection_parsed(selection_id, result, status="proposed")
        _send_plan(client, dm_channel, selection_id, result, sel["freeform"])
    except Exception as e:
        client.chat_postMessage(
            channel=dm_channel,
            text=":warning: Refinement failed (%s: %s) — the previous plan "
                 "still stands." % (type(e).__name__, e),
        )


def handle_retry(selection_id, client, dm_channel):
    """Re-run the concierge on a saved-but-unparsed selection (Retry button)."""
    sel = store.get_selection(selection_id)
    if not sel or not sel["freeform"]:
        client.chat_postMessage(channel=dm_channel, text="🤔 Can't find that order any more.")
        return
    client.chat_postMessage(channel=dm_channel, text=":mag: Retrying...")
    try:
        result = concierge.plan(sel["user_slack_id"], sel["freeform"], sel["half"])
        if result.get("rejected"):
            client.chat_postMessage(channel=dm_channel, text=":no_good: %s" % result["rejected"])
            return
        store.update_selection_parsed(selection_id, result, status="proposed")
        _send_plan(client, dm_channel, selection_id, result, sel["freeform"])
    except Exception as e:
        client.chat_postMessage(
            channel=dm_channel,
            text=":warning: Still couldn't do it (%s). Try rewording with /order." % type(e).__name__,
        )


def on_plan_accepted(week=None):
    """After an accept, rebuild draft baskets so the dashboard updates live."""
    try:
        store.build_baskets(week or _current_week())
    except Exception as e:
        print("[plan] build_baskets failed (non-fatal): %s" % e, flush=True)


def prefilled_order_modal(selection_id):
    """The /order modal pre-filled from an existing selection (legacy Fix it button)."""
    from slack_surface.handlers import _order_modal
    sel = store.get_selection(selection_id)
    modal = _order_modal()
    if sel:
        modal["blocks"][0]["element"]["initial_value"] = sel["freeform"] or ""
        half = sel["half"] or "early"
        label = "Early week (Mon)" if half == "early" else "Late week (Wed)"
        modal["blocks"][1]["element"]["initial_option"] = {
            "text": {"type": "plain_text", "text": label}, "value": half}
    return modal


# Team decision: no delivery tracking — /order writes selections, and the
# Friday check-in works directly off what each person ordered.
