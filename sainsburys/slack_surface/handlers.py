import grocery
import store
from flows import basket, rescue
from flows.basket import _current_week


def register(app):

    @app.command("/order")
    def order(ack, client, body):
        ack()
        modal = _order_modal()
        modal["private_metadata"] = body["channel_id"]
        client.views_open(trigger_id=body["trigger_id"], view=modal)

    @app.view("order_submit")
    def on_order_submit(ack, body, client):
        ack()
        basket.handle_order_submit(body, client)

    # ── /suggest = alias for /order (one unified flow) ──────────────────────────

    @app.command("/suggest")
    def suggest(ack, client, body):
        ack()
        modal = _order_modal()
        modal["private_metadata"] = body["channel_id"]
        client.views_open(trigger_id=body["trigger_id"], view=modal)

    @app.action("suggestion_accept")
    def on_suggestion_accept(ack, respond, body, client):
        ack()

        def _go():
            import json as _json
            selection_id = int(body["actions"][0]["value"])
            store.accept_selection(selection_id)
            basket.on_plan_accepted()
            # Swap to the ordered view — the plan stays amendable via Change something
            respond({"blocks": basket.plan_view_blocks(selection_id, ordered=True),
                     "text": "✅ Ordered — you can still change it.",
                     "replace_original": True})
            # Human confirmed the plan → fill the real Sainsbury's trolley
            sel = store.get_selection(selection_id)
            if sel and sel.get("parsed"):
                basket.push_selection_to_trolley(client, _channel_id(body),
                                                 _json.loads(sel["parsed"]))

        _run(respond, _go)

    @app.action("suggestion_refine")
    def on_suggestion_refine(ack, respond, body, client):
        ack()

        def _go():
            selection_id = body["actions"][0]["value"]
            client.views_open(trigger_id=body["trigger_id"],
                              view=_refine_modal(selection_id))

        _run(respond, _go)

    @app.view("refine_submit")
    def on_refine_submit(ack, body, client):
        ack()
        basket.handle_refine_submit(body, client)

    # ── /authenticate (reconnect a stale Sainsbury's session) ───────────────────

    @app.command("/authenticate")
    def authenticate(ack, client, body):
        ack()
        client.views_open(trigger_id=body["trigger_id"], view=_authenticate_modal())

    @app.view("authenticate_submit")
    def on_authenticate_submit(ack, body, client):
        # ack() FIRST: start_login() drives a real browser (multiple waits
        # adding up to 10-20s+) — Slack needs the view_submission acked within
        # 3s or the modal shows "trouble connecting", even though the work
        # below finishes fine. Same reasoning as on_authenticate_mfa_submit.
        ack()
        values = body["view"]["state"]["values"]
        email = values["auth_email"]["email"].get("value", "").strip()
        password = values["auth_password"]["password"].get("value", "") or ""
        user_id = body["user"]["id"]

        try:
            result = grocery.start_login(email, password)
        except Exception as e:
            _dm(client, user_id, "❌ Couldn't reach the login helper: %s. Run /authenticate to try again." % e)
            return

        if result.get("status") == "mfa_required":
            # No fresh trigger_id is available this long after the original
            # one expired, so prompt via a button click instead of pushing a
            # modal directly — the button click hands us a new trigger_id.
            _dm(client, user_id, "📱 Check your phone for the 6-digit Sainsbury's code.",
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn",
                     "text": "📱 Check your phone for the 6-digit Sainsbury's code."}},
                    {"type": "actions", "elements": [
                        {"type": "button", "style": "primary",
                         "text": {"type": "plain_text", "text": "Enter code"},
                         "action_id": "authenticate_enter_mfa", "value": result["handle"]},
                    ]},
                ])
            return

        _dm(client, user_id, "✅ Sainsbury's connected — trolley pushes will work again.")

    @app.action("authenticate_enter_mfa")
    def on_authenticate_enter_mfa(ack, body, client):
        ack()
        handle = body["actions"][0]["value"]
        client.views_open(trigger_id=body["trigger_id"], view=_authenticate_mfa_modal(handle))

    @app.view("authenticate_mfa_submit")
    def on_authenticate_mfa_submit(ack, body, client):
        # Same ack-first reasoning as on_authenticate_submit — submit_mfa()
        # also waits on a real page redirect.
        ack()
        handle = body["view"]["private_metadata"]
        values = body["view"]["state"]["values"]
        code = values["auth_mfa_code"]["code"].get("value", "").strip()
        user_id = body["user"]["id"]

        try:
            result = grocery.submit_mfa(handle, code)
        except Exception as e:
            _dm(client, user_id, "❌ %s: %s. Run /authenticate to try again." % (type(e).__name__, e))
            return

        if result.get("status") == "ok":
            _dm(client, user_id, "✅ Sainsbury's connected — trolley pushes will work again.")
        else:
            _dm(client, user_id, "❌ %s Run /authenticate to try again."
                                 % result.get("message", "MFA verification failed."))

    # ── /demo-aggregate (post the week's consolidated basket) ────────────────────

    @app.command("/demo-aggregate")
    def demo_aggregate(ack, respond, client, body):
        ack()
        channel = body["channel_id"]

        def _go():
            from slack_surface import blocks as blk
            week = _current_week()
            orders = store.build_baskets(week)
            if not orders:
                respond({"text": "Nothing ordered yet this week.",
                         "response_type": "ephemeral", "replace_original": False})
                return
            client.chat_postMessage(
                channel=channel,
                text="This week's basket",
                blocks=blk.basket_blocks(orders[0]),
                unfurl_links=False, unfurl_media=False,
            )
            respond({"text": "Posted this week's basket.",
                     "response_type": "ephemeral", "replace_original": False})

        _run(respond, _go)

    # ── Order confirmation DM buttons ────────────────────────────────────────────

    @app.action("order_confirm")
    def on_order_confirm(ack, respond, body, client):
        ack()

        def _go():
            import json as _json
            selection_id = int(body["actions"][0]["value"])
            store.confirm_selection(selection_id)
            _replace_actions(respond, body, "✅ Confirmed — adding to the Sainsbury's trolley…")
            sel = store.get_selection(selection_id)
            if sel and sel.get("parsed"):
                basket.push_selection_to_trolley(client, _channel_id(body),
                                                 _json.loads(sel["parsed"]))

        _run(respond, _go)

    @app.action("order_fix")
    def on_order_fix(ack, respond, body, client):
        ack()

        def _go():
            selection_id = int(body["actions"][0]["value"])
            modal = basket.prefilled_order_modal(selection_id)
            store.void_selection(selection_id)
            _replace_actions(respond, body, "✏️ Superseded — check the new confirmation.")
            client.views_open(trigger_id=body["trigger_id"], view=modal)

        _run(respond, _go)

    @app.action("order_retry")
    def on_order_retry(ack, respond, body, client):
        ack()

        def _go():
            selection_id = int(body["actions"][0]["value"])
            _replace_actions(respond, body, "🔁 Retrying...")
            basket.handle_retry(selection_id, client, _channel_id(body))

        _run(respond, _go)

    # ── /demo-checkin (mirrors the real Fri 09:30 trigger) ──────────────────────

    @app.command("/demo-checkin")
    def demo_checkin(ack, respond, client):
        ack()

        def _go():
            sent = rescue.send_checkin_dms(client)
            respond({"text": "📬 Check-in DMs sent to %d user(s)." % sent,
                     "response_type": "ephemeral", "replace_original": False})

        _run(respond, _go)

    @app.action("checkin_ate")
    def on_checkin_ate(ack, respond, body, client):
        ack()
        _run(respond, lambda: _record_checkin(respond, body, client, fraction=1.0))

    @app.action("checkin_some")
    def on_checkin_some(ack, respond, body, client):
        ack()
        _run(respond, lambda: _record_checkin(respond, body, client, fraction=0.5))

    @app.action("checkin_none")
    def on_checkin_none(ack, respond, body, client):
        ack()
        _run(respond, lambda: _record_checkin(respond, body, client, fraction=0.0))

    # ── /demo-rescue (mirrors the real Fri 11:30 trigger) ───────────────────────

    @app.command("/demo-rescue")
    def demo_rescue(ack, respond, client, body):
        ack()
        _run(respond, lambda: rescue.post_board(client, body["channel_id"]))

    @app.action("claim")
    def on_claim(ack, respond, body, client):
        ack()

        def _claim():
            product_id = int(body["actions"][0]["value"])
            user = body["user"]["id"]
            try:
                result = store.claim_product(product_id, user)
            except ValueError:
                respond({"text": "😅 Too slow — nothing left of that one. "
                                 "Run `/demo-rescue` for the latest board.",
                         "response_type": "ephemeral", "replace_original": False})
                return
            total = store.claimed_total()
            client.chat_postMessage(
                channel=_channel_id(body),
                thread_ts=body["message"]["ts"],
                text="🛟 <@%s> rescued *%s* — £%.2f saved from the bin! 💚  "
                     "Running total this week: *£%.2f*" % (
                    user, result["name"], result["value"], total),
            )
            # Re-render the board in place so claimed-out items disappear
            board = rescue.board_blocks()
            client.chat_update(
                channel=_channel_id(body),
                ts=body["message"]["ts"],
                text="🛟 Rescue board",
                blocks=board if board else [{"type": "section", "text": {
                    "type": "mrkdwn", "text": "🎉 *Everything rescued — fridge cleared!*"}}],
            )

        _run(respond, _claim)

    # ── /demo-sweep (end-of-week waste sweep + digest) ────────────────────────────

    @app.command("/demo-sweep")
    def demo_sweep(ack, respond, client, body):
        ack()
        channel = body["channel_id"]

        def _go():
            from slack_surface import blocks as blk
            week = _current_week()
            digest = store.sweep_waste(week)
            client.chat_postMessage(
                channel=channel,
                text="🗑️ Weekly waste sweep",
                blocks=blk.digest_blocks(digest),
            )
            board = store.leaderboard()
            if board:
                lb_text = "\n".join(
                    "%s. *%s* — £%.2f saved" % (i + 1, row["name"], row["saved"])
                    for i, row in enumerate(board[:5])
                )
                client.chat_postMessage(channel=channel,
                                        text="🏆 *Rescue leaderboard:*\n" + lb_text)
            respond({"text": "Sweep done.",
                     "response_type": "ephemeral", "replace_original": False})

        _run(respond, _go)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run(respond, thunk):
    """Run a handler body; report missing store implementations instead of crashing."""
    try:
        thunk()
    except NotImplementedError:
        respond({"text": "⏳ Not wired up yet — waiting on a store.py implementation.",
                 "response_type": "ephemeral", "replace_original": False})
    except Exception as e:
        respond({"text": "⚠️ %s: %s" % (type(e).__name__, e),
                 "response_type": "ephemeral", "replace_original": False})


def _dm(client, user_id, text, blocks=None):
    dm = client.conversations_open(users=user_id)
    client.chat_postMessage(channel=dm["channel"]["id"], text=text, blocks=blocks)


def _channel_id(body):
    channel = body.get("channel") or {}
    return channel.get("id") or body["container"]["channel_id"]


def _replace_actions(respond, body, note, value=None):
    """Swap the (matching) actions block of the source message for a context note."""
    new_blocks = []
    for block in body["message"]["blocks"]:
        if block.get("type") == "actions" and (
            value is None
            or any(e.get("value") == value for e in block.get("elements", []))
        ):
            new_blocks.append({"type": "context",
                               "elements": [{"type": "mrkdwn", "text": note}]})
        else:
            new_blocks.append(block)
    respond({"blocks": new_blocks, "text": note, "replace_original": True})
    return new_blocks


def _record_checkin(respond, body, client, fraction):
    raw = body["actions"][0]["value"]          # "product_id:qty" (older DMs: just id)
    product_id, _, qty_str = raw.partition(":")
    product_id, qty_ordered = int(product_id), float(qty_str or 1)
    user = body["user"]["id"]
    try:
        result = store.record_consumption(user, product_id, fraction, qty_ordered)
    except ValueError:
        # Stale DM: sent before a reset/refactor, or by a bot instance with a
        # different local lunch.db — its button ids don't resolve here.
        respond({"text": "🤔 That button is from an older check-in and I can't match "
                         "it any more. Run `/demo-checkin` for a fresh one.",
                 "response_type": "ephemeral", "replace_original": False})
        return

    label = {1.0: "✅ Ate it", 0.5: "🥡 Some left", 0.0: "🙈 Didn't touch"}[fraction]
    new_blocks = _replace_actions(respond, body, "%s — *%s*" % (label, result["name"]), value=raw)

    # All items answered? Post the weekly wrap-up.
    if not any(b.get("type") == "actions" for b in new_blocks):
        from flows.basket import _current_week
        summary = store.user_week_summary(user, _current_week())
        client.chat_postMessage(
            channel=_channel_id(body),
            thread_ts=body["message"]["ts"],
            text="🧾 All done! You ate *£%.2f* of your *£%.2f* order this week. "
                 "Whatever's left goes on the rescue board 🛟" % (
                summary["eaten_value"], summary["ordered_value"]),
        )


def _refine_modal(selection_id):
    return {
        "type": "modal",
        "callback_id": "refine_submit",
        "private_metadata": str(selection_id),
        "title": {"type": "plain_text", "text": "Change something"},
        "submit": {"type": "plain_text", "text": "Re-suggest"},
        "blocks": [
            {
                "type": "input",
                "block_id": "refine_text",
                "label": {"type": "plain_text", "text": "What should be different?"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "feedback",
                    "multiline": True,
                    "placeholder": {"type": "plain_text",
                                    "text": "e.g. no fish, add a drink, something more filling"},
                },
            },
        ],
    }


def _authenticate_modal():
    return {
        "type": "modal",
        "callback_id": "authenticate_submit",
        "title": {"type": "plain_text", "text": "Reconnect Sainsbury's"},
        "submit": {"type": "plain_text", "text": "Log in"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn",
                         "text": "Slack can't mask this field — anyone who can see your "
                                 "screen while you type sees it in plain text."},
            },
            {
                "type": "input",
                "block_id": "auth_email",
                "label": {"type": "plain_text", "text": "Sainsbury's email"},
                "element": {"type": "plain_text_input", "action_id": "email"},
            },
            {
                "type": "input",
                "block_id": "auth_password",
                "label": {"type": "plain_text", "text": "Password"},
                "element": {"type": "plain_text_input", "action_id": "password"},
            },
        ],
    }


def _authenticate_mfa_modal(handle):
    return {
        "type": "modal",
        "callback_id": "authenticate_mfa_submit",
        "private_metadata": handle,
        "title": {"type": "plain_text", "text": "Enter your code"},
        "submit": {"type": "plain_text", "text": "Confirm"},
        "blocks": [
            {
                "type": "input",
                "block_id": "auth_mfa_code",
                "label": {"type": "plain_text", "text": "6-digit code sent to your phone"},
                "element": {"type": "plain_text_input", "action_id": "code"},
            },
        ],
    }


def _order_modal():
    return {
        "type": "modal",
        "callback_id": "order_submit",
        "title": {"type": "plain_text", "text": "Order lunch"},
        "submit": {"type": "plain_text", "text": "Order"},
        "blocks": [
            {
                "type": "input",
                "block_id": "order_text",
                "optional": True,
                "label": {"type": "plain_text", "text": "What do you want?"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "text",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "An exact order, a mood (“something light”), or leave blank and I'll pick",
                    },
                },
            },
        ],
    }
