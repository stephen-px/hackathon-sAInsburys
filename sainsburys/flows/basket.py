import json

import grocery
import store
from agents import parser as parser_agent
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


def _send_confirmation(client, dm_channel, selection_id, result, order_text, half):
    product_ids = [line["product_id"] for line in result.get("product_lines", [])]
    products = {p["id"]: p for p in store.get_products_by_ids(product_ids)}
    lines_text = _format_lines(result.get("product_lines", []), products)
    notes = result.get("notes") or ""
    client.chat_postMessage(
        channel=dm_channel,
        text="Order logged for %s week: %s" % (half, lines_text),
        blocks=blocks.order_confirmation_blocks(selection_id, half, lines_text, notes, order_text),
        unfurl_links=False, unfurl_media=False,
    )


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

        if result.get("rejected"):
            print("[order] rejected: %s" % result["rejected"], flush=True)
            client.chat_postMessage(
                channel=dm_channel,
                text=":no_good: %s\n_Your request: \"%s\"_" % (result["rejected"], order_text),
            )
            return

        row = store.record_selection(user_id, week, half, freeform=order_text, parsed=result)
        print("[order] recorded selection id=%s lines=%s" % (row["id"], result.get("product_lines")), flush=True)
        # Rebuild draft baskets so the dashboard shows the updated basket immediately
        try:
            store.build_baskets(week)
        except Exception as e:
            print("[order] build_baskets failed (non-fatal): %s" % e, flush=True)

        _send_confirmation(client, dm_channel, row["id"], result, order_text, half)
        # Trolley push happens when the user taps "Looks right ✅" (order_confirm)
        # — the parsed plan must be human-confirmed before touching the real basket.

    except Exception as e:
        row = store.record_selection(user_id, week, half, freeform=order_text)
        print("[order] parse failed (%s), saved raw as id=%s" % (e, row["id"]), flush=True)
        client.chat_postMessage(
            channel=dm_channel,
            text="Couldn't parse your order — saved the raw request.",
            blocks=blocks.order_failure_blocks(row["id"], order_text, "%s: %s" % (type(e).__name__, e)),
        )


def handle_retry(selection_id, client, dm_channel):
    """Re-run the parser on a saved-but-unparsed selection (Retry button)."""
    sel = store.get_selection(selection_id)
    if not sel or not sel["freeform"]:
        client.chat_postMessage(channel=dm_channel, text="🤔 Can't find that order any more.")
        return
    client.chat_postMessage(channel=dm_channel, text=":mag: Retrying the parse...")
    try:
        result = parser_agent.parse(sel["user_slack_id"], sel["freeform"], sel["half"])
        if result.get("rejected"):
            client.chat_postMessage(channel=dm_channel, text=":no_good: %s" % result["rejected"])
            return
        store.update_selection_parsed(selection_id, result)
        _send_confirmation(client, dm_channel, selection_id, result, sel["freeform"], sel["half"])
    except Exception as e:
        client.chat_postMessage(
            channel=dm_channel,
            text=":warning: Still couldn't parse it (%s). Try rewording with /order." % type(e).__name__,
        )


def prefilled_order_modal(selection_id):
    """The /order modal pre-filled from an existing selection (Fix it button)."""
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


# ── /suggest: open suggestions with an accept/refine loop ──────────────────────

def _send_suggestion(client, dm_channel, selection_id, result, mood):
    product_ids = [line["product_id"] for line in result.get("product_lines", [])]
    products = {p["id"]: p for p in store.get_products_by_ids(product_ids)}
    lines_text = _format_lines(result.get("product_lines", []), products)
    client.chat_postMessage(
        channel=dm_channel,
        text="Suggestion: %s" % (result.get("notes") or lines_text),
        blocks=blocks.suggestion_blocks(selection_id, lines_text,
                                        result.get("notes") or "", mood),
        unfurl_links=False, unfurl_media=False,
    )


def handle_suggest_submit(body, client):
    from agents import suggester
    user_id = body["user"]["id"]
    user_name = body["user"].get("username", body["user"].get("name", user_id))
    values = body["view"]["state"]["values"]
    mood = (values["suggest_mood"]["mood"].get("value") or "").strip()
    half = values["suggest_half"]["half"]["selected_option"]["value"]
    week = _current_week()

    store.ensure_user(user_id, user_name)
    dm = client.conversations_open(users=user_id)
    dm_channel = dm["channel"]["id"]
    client.chat_postMessage(channel=dm_channel, text=":bulb: Thinking up a lunch for you...")

    print("[suggest] user=%s half=%s mood=%r" % (user_id, half, mood), flush=True)
    try:
        result = suggester.suggest(user_id, mood, half)
        if result.get("rejected"):
            client.chat_postMessage(channel=dm_channel, text=":no_good: %s" % result["rejected"])
            return
        row = store.record_selection(user_id, week, half, freeform=mood or "(surprise me)",
                                     parsed=result, status="proposed")
        print("[suggest] proposed selection id=%s" % row["id"], flush=True)
        _send_suggestion(client, dm_channel, row["id"], result, mood)
    except Exception as e:
        client.chat_postMessage(
            channel=dm_channel,
            text=":warning: Couldn't come up with a suggestion (%s: %s) — try again "
                 "or use /order directly." % (type(e).__name__, e),
        )


def handle_refine_submit(body, client):
    """User told us what to change about a proposed suggestion."""
    from agents import suggester
    selection_id = int(body["view"]["private_metadata"])
    feedback = body["view"]["state"]["values"]["refine_text"]["feedback"]["value"]
    user_id = body["user"]["id"]

    dm = client.conversations_open(users=user_id)
    dm_channel = dm["channel"]["id"]

    sel = store.get_selection(selection_id)
    if not sel or sel["status"] != "proposed":
        client.chat_postMessage(channel=dm_channel,
                                text="🤔 That suggestion is gone — run /suggest again.")
        return

    client.chat_postMessage(channel=dm_channel, text=":bulb: Reworking it...")
    print("[suggest] refine id=%s feedback=%r" % (selection_id, feedback), flush=True)
    try:
        previous = json.loads(sel["parsed"]) if sel["parsed"] else None
        result = suggester.suggest(user_id, sel["freeform"], sel["half"],
                                   previous=previous, feedback=feedback)
        if result.get("rejected"):
            client.chat_postMessage(channel=dm_channel, text=":no_good: %s" % result["rejected"])
            return
        store.update_selection_parsed(selection_id, result, status="proposed")
        _send_suggestion(client, dm_channel, selection_id, result, sel["freeform"])
    except Exception as e:
        client.chat_postMessage(
            channel=dm_channel,
            text=":warning: Refinement failed (%s: %s) — the previous suggestion "
                 "still stands." % (type(e).__name__, e),
        )


# Team decision: no delivery tracking — /order writes selections, and the
# Friday check-in works directly off what each person ordered.


# ── Real Sainsbury's trolley push (add-to-basket only, never checkout) ─────────

def push_to_trolley(order_id):
    """Add an approved order's lines to the real sainsburys.co.uk trolley.

    Newly resolved product uids/urls are cached back onto products so the
    next push (and product links) skip the search round-trip.
    Returns grocery.push_lines()'s result dict."""
    lines = store.order_lines(order_id)
    result = grocery.push_lines(lines)
    for product_id, (uid, url) in result["resolved"].items():
        store.set_product_sainsburys(product_id, uid, url)
    return result


def push_selection_to_trolley(client, dm_channel, result):
    """Add one parsed selection's lines to the real trolley, DM the outcome.

    Runs at /order (and suggestion-accept) time — the trolley IS the basket.
    No session → quiet skip with a hint. Never books a slot or checks out."""
    product_lines = result.get("product_lines") or []
    if not product_lines:
        return
    try:
        grocery._load_session()
    except grocery.NotConnected as e:
        print("[trolley] push skipped: %s" % e, flush=True)
        return
    products = {p["id"]: p for p in store.get_products_by_ids(
        [l["product_id"] for l in product_lines])}
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
