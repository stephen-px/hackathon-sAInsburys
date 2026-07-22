import store
from flows import basket, rescue


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
    def on_checkin_ate(ack, respond, body):
        ack()
        _run(respond, lambda: _record_checkin(respond, body, fraction=1.0))

    @app.action("checkin_some")
    def on_checkin_some(ack, respond, body):
        ack()
        _run(respond, lambda: _record_checkin(respond, body, fraction=0.5))

    @app.action("checkin_none")
    def on_checkin_none(ack, respond, body):
        ack()
        _run(respond, lambda: _record_checkin(respond, body, fraction=0.0))

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
            client.chat_postMessage(
                channel=body["channel"]["id"],
                thread_ts=body["message"]["ts"],
                text="🛟 <@%s> rescued *%s* — £%.2f saved from the bin! 💚" % (
                    user, result["name"], result["value"]),
            )

        _run(respond, _claim)


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


def _record_checkin(respond, body, fraction):
    product_id = int(body["actions"][0]["value"])
    user = body["user"]["id"]
    try:
        result = store.record_consumption(user, product_id, fraction)
    except ValueError:
        # Stale DM: sent before a reset/refactor, or by a bot instance with a
        # different local lunch.db — its button ids don't resolve here.
        respond({"text": "🤔 That button is from an older check-in and I can't match "
                         "it any more. Run `/demo-checkin` for a fresh one.",
                 "response_type": "ephemeral", "replace_original": False})
        return
    label = {1.0: "Ate it", 0.5: "Some left", 0.0: "Didn't touch"}[fraction]
    respond({"text": "Logged for *%s*: %s ✅" % (result["name"], label),
             "response_type": "ephemeral", "replace_original": False})


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
                "label": {"type": "plain_text", "text": "What do you want?"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "text",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g. 3 days of chicken wraps, one smoked salmon pitta, no dairy",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "order_half",
                "label": {"type": "plain_text", "text": "Delivery"},
                "element": {
                    "type": "static_select",
                    "action_id": "half",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Early week (Mon)"}, "value": "early"},
                        {"text": {"type": "plain_text", "text": "Late week (Wed)"}, "value": "late"},
                    ],
                },
            },
        ],
    }
