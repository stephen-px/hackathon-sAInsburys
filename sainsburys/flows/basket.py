import json

import grocery
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
        lines.append("• {qty}x *{name}* — £{cost:.2f}".format(
            qty=line["qty"], name=blocks.plink(name, product.get("url")), cost=cost))
    return "\n".join(lines)


def _send_plan(client, dm_channel, selection_id, result, request_text, ordered=False):
    """DM the plan. Proposed → Order it / Change; ordered → amendable Change."""
    product_ids = [line["product_id"] for line in result.get("product_lines", [])]
    products = {p["id"]: p for p in store.get_products_by_ids(product_ids)}
    lines_text = _format_lines(result.get("product_lines", []), products)
    client.chat_postMessage(
        channel=dm_channel,
        text="%s: %s" % ("Your order" if ordered else "Proposed lunch",
                         result.get("notes") or lines_text),
        blocks=blocks.suggestion_blocks(selection_id, lines_text,
                                        result.get("notes") or "", request_text,
                                        ordered=ordered),
        unfurl_links=False, unfurl_media=False,
    )


def plan_view_blocks(selection_id, ordered):
    """Rebuild the plan DM blocks for an existing selection (used on Accept)."""
    sel = store.get_selection(selection_id)
    parsed = json.loads(sel["parsed"]) if sel and sel["parsed"] else {}
    product_ids = [line["product_id"] for line in parsed.get("product_lines", [])]
    products = {p["id"]: p for p in store.get_products_by_ids(product_ids)}
    lines_text = _format_lines(parsed.get("product_lines", []), products)
    return blocks.suggestion_blocks(selection_id, lines_text,
                                    parsed.get("notes") or "",
                                    sel["freeform"] if sel else "", ordered=ordered)


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
    # Delivery halves were dropped from the UX — everything is one weekly basket.
    half = "early"
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
        # Trolley push happens when the user taps "Order it ✅" — the plan must
        # be human-confirmed before touching the real basket.
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
    if not sel or sel["status"] == "void":
        client.chat_postMessage(channel=dm_channel,
                                text="🤔 That plan is gone — run /order again.")
        return

    # Amending an already-placed order keeps it placed; a proposal stays a proposal.
    ordered = sel["status"] != "proposed"
    keep_status = "proposed" if not ordered else \
        ("pending" if sel["status"] == "ordered" else sel["status"])

    client.chat_postMessage(channel=dm_channel, text=":bulb: Reworking it...")
    print("[plan] refine id=%s ordered=%s feedback=%r" % (selection_id, ordered, feedback), flush=True)
    try:
        previous = json.loads(sel["parsed"]) if sel["parsed"] else None
        result = concierge.plan(user_id, sel["freeform"], sel["half"],
                                previous=previous, feedback=feedback)
        if result.get("rejected"):
            client.chat_postMessage(channel=dm_channel, text=":no_good: %s" % result["rejected"])
            return
        store.update_selection_parsed(selection_id, result, status=keep_status)
        if ordered:
            on_plan_accepted()   # order changed — refresh draft baskets for the dashboard
        _send_plan(client, dm_channel, selection_id, result, sel["freeform"], ordered=ordered)
        if ordered:
            # The previous version of this order was already pushed to the real
            # trolley; we never remove items, so flag the drift for a human.
            client.chat_postMessage(
                channel=dm_channel,
                text="♻️ Order changed after it was placed — <%s|check your "
                     "Sainsbury's trolley>: earlier items may need removing "
                     "or swapping by hand." % grocery.TROLLEY_URL,
                unfurl_links=False, unfurl_media=False)
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
    return modal


# Team decision: no delivery tracking — /order writes selections, and the
# Friday check-in works directly off what each person ordered.


# ── Real Sainsbury's trolley push (add-to-basket only, never checkout) ─────────

def push_selection_to_trolley(client, dm_channel, result):
    """Add one parsed selection's lines to the real trolley, DM the outcome.

    Runs when the user taps "Order it ✅" — human confirms the plan, then the
    trolley fills. No session → DM the user to reconnect. Never books a slot
    or checks out."""
    product_lines = result.get("product_lines") or []
    if not product_lines:
        return
    products = {p["id"]: p for p in store.get_products_by_ids(
        [l["product_id"] for l in product_lines])}
    try:
        grocery._load_session()
    except grocery.NotConnected as e:
        client.chat_postMessage(
            channel=dm_channel,
            text="⚠️ Sainsbury's session is stale — this order wasn't pushed to the "
                 "real trolley. Run */authenticate* to reconnect, then tap *Order it* "
                 "again — or add these yourself on sainsburys.co.uk for now:\n"
                 + _format_lines(product_lines, products),
            unfurl_links=False, unfurl_media=False,
        )
        print("[trolley] push skipped: %s" % e, flush=True)
        return
    lines = [{"product_id": l["product_id"],
              "name": products.get(l["product_id"], {}).get("name", ""),
              "qty": l["qty"],
              "sainsburys_uid": products.get(l["product_id"], {}).get("sainsburys_uid")}
             for l in product_lines if l["product_id"] in products]
    try:
        outcome = grocery.push_lines(lines)
        for product_id, (uid, url) in outcome["resolved"].items():
            store.set_product_sainsburys(product_id, uid, url)
        client.chat_postMessage(channel=dm_channel,
                                text=trolley_summary_text(outcome),
                                unfurl_links=False, unfurl_media=False)
        print("[trolley] added=%d failed=%d" % (len(outcome["added"]), len(outcome["failed"])),
              flush=True)
    except Exception as e:
        print("[trolley] push failed: %s: %s" % (type(e).__name__, e), flush=True)
        client.chat_postMessage(
            channel=dm_channel,
            text="⚠️ Couldn't add to the real Sainsbury's trolley (%s) — your order "
                 "is still logged." % type(e).__name__)


def trolley_summary_text(result):
    """One Slack mrkdwn blob summarising a trolley push. Always ends with the
    trolley link so the user can verify their selection landed."""
    added, failed = result["added"], result["failed"]
    parts = []
    if added:
        total = " (trolley now £%.2f)" % result["total"] if result["total"] is not None else ""
        parts.append("🛒 Added *%d item%s* to the real Sainsbury's trolley%s:"
                     % (len(added), "" if len(added) == 1 else "s", total))
        parts.extend("  • %g× %s" % (a["qty"], a["name"]) for a in added)
    if failed:
        parts.append("⚠️ Couldn't add: " + ", ".join(
            "%s ×%d (%s)" % (f["name"], f["qty"], f["reason"]) for f in failed))
    if not parts:
        parts.append("Nothing to push — order has no lines.")
    parts.append("👀 <%s|Open your Sainsbury's trolley> to check it landed."
                 % result["trolley_url"])
    return "\n".join(parts)
