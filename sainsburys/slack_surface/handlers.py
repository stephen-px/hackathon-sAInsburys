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

    # ── /suggest = alias for /order (one unified flow) ──────────────────────────

    @app.command("/suggest")
    def suggest(ack, client, body):
        ack()
        modal = _order_modal()
        modal["private_metadata"] = body["channel_id"]
        client.views_open(trigger_id=body["trigger_id"], view=modal)

    @app.action("suggestion_accept")
    def on_suggestion_accept(ack, respond, body):
        ack()

        def _go():
            selection_id = int(body["actions"][0]["value"])
            store.accept_selection(selection_id)
            basket.on_plan_accepted()
            # Swap to the ordered view — the plan stays amendable via Change something
            respond({"blocks": basket.plan_view_blocks(selection_id, ordered=True),
                     "text": "✅ Ordered — you can still change it.",
                     "replace_original": True})

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

    # ── Order confirmation DM buttons ────────────────────────────────────────────

    @app.action("order_confirm")
    def on_order_confirm(ack, respond, body):
        ack()

        def _go():
            store.confirm_selection(int(body["actions"][0]["value"]))
            _replace_actions(respond, body, "✅ Confirmed — enjoy!")

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

    # ── /reset (end-of-week sweep: waste logged & scored, orders wiped) ─────────

    @app.command("/reset")
    def reset(ack, respond, client, body):
        ack()

        def _go():
            from slack_surface import blocks as blk
            digest = store.sweep_waste()
            store.wipe_orders()
            print("[reset] wasted £%.2f across %d items; orders wiped"
                  % (digest["wasted_value"], digest["wasted_items"]), flush=True)
            client.chat_postMessage(
                channel=body["channel_id"],
                text="🗑️ Weekly sweep: £%.2f wasted. Fresh week started." % digest["wasted_value"],
                blocks=blk.digest_blocks(digest),
            )
            board = store.leaderboard()
            if board:
                lb_text = "\n".join(
                    "%s. *%s* — £%.2f net (£%.2f saved / £%.2f wasted)" % (
                        i + 1, row["name"], row["net"], row["claimed"], row["wasted"])
                    for i, row in enumerate(board[:5])
                )
                client.chat_postMessage(channel=body["channel_id"],
                                        text="🏆 *Leaderboard:*\n" + lb_text)

        _run(respond, _go)

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
