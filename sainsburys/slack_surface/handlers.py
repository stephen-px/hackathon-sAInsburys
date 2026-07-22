from flows import basket, rescue


def register(app):

    # ── Demo slash commands ────────────────────────────────────────────────────

    @app.command("/demo-suggest")
    def demo_suggest(ack, client, body):
        ack()
        channel = body["channel_id"]
        basket.post_picker(client, channel)

    @app.command("/demo-aggregate")
    def demo_aggregate(ack, client, body):
        ack()
        channel = body["channel_id"]
        basket.aggregate_and_post(client, channel)

    @app.command("/demo-deliver")
    def demo_deliver(ack, client, body):
        ack()
        channel = body["channel_id"]
        basket.simulate_delivery(client, channel)

    @app.command("/demo-checkin")
    def demo_checkin(ack, client):
        ack()
        rescue.send_checkin_dms(client)

    @app.command("/demo-rescue")
    def demo_rescue(ack, client, body):
        ack()
        channel = body["channel_id"]
        rescue.post_board(client, channel)

    @app.command("/demo-sweep")
    def demo_sweep(ack, client, body):
        ack()
        channel = body["channel_id"]
        rescue.sweep_and_digest(client, channel)

    @app.command("/demo-reset")
    def demo_reset(ack, client, body):
        ack()
        from data import demo_reset as dr
        dr.reset()
        client.chat_postMessage(channel=body["channel_id"], text="Demo state reset. Fresh week seeded.")

    # ── Actions ────────────────────────────────────────────────────────────────

    @app.action("meal_pick_early")
    def on_meal_pick_early(ack, body, client):
        ack()
        _handle_meal_pick(body, client, half="early")

    @app.action("meal_pick_late")
    def on_meal_pick_late(ack, body, client):
        ack()
        _handle_meal_pick(body, client, half="late")

    @app.action("freeform_open")
    def on_freeform_open(ack, client, body):
        ack()
        client.views_open(trigger_id=body["trigger_id"], view=_freeform_modal())

    @app.view("freeform_submit")
    def on_freeform_submit(ack, body, client):
        ack()
        from flows.basket import handle_freeform_submit
        handle_freeform_submit(body, client)

    @app.action("approve_order")
    def on_approve_order(ack, body, client):
        ack()
        order_id = int(body["actions"][0]["value"])
        basket.approve(order_id, body, client)

    @app.action("claim")
    def on_claim(ack, body, client):
        ack()
        import store
        lot_id = int(body["actions"][0]["value"])
        user = body["user"]["id"]
        result = store.claim_lot(lot_id, user)
        client.chat_postMessage(
            channel=body["channel"]["id"],
            thread_ts=body["message"]["ts"],
            text=f"<@{user}> rescued *{result['name']}* — £{result['value']:.2f} saved!",
        )

    @app.action("checkin_ate")
    def on_checkin_ate(ack, body, client):
        ack()
        _record_checkin(body, client, fraction=1.0)

    @app.action("checkin_some")
    def on_checkin_some(ack, body, client):
        ack()
        _record_checkin(body, client, fraction=0.5)

    @app.action("checkin_none")
    def on_checkin_none(ack, body, client):
        ack()
        _record_checkin(body, client, fraction=0.0)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _handle_meal_pick(body, client, half):
    import store
    from datetime import date
    meal_id = int(body["actions"][0]["value"])
    user = body["user"]["id"]
    week = _current_week()
    store.record_selection(user, week, half, meal_id=meal_id)
    client.chat_postMessage(
        channel=body["channel"]["id"],
        thread_ts=body["message"]["ts"],
        text=f"Got it <@{user}> — logged for {half} week.",
    )


def _record_checkin(body, client, fraction):
    import store
    lot_id = int(body["actions"][0]["value"])
    user = body["user"]["id"]
    store.record_consumption(user, lot_id, fraction)


def _current_week():
    from datetime import date, timedelta
    today = date.today()
    return today - timedelta(days=today.weekday())


def _freeform_modal():
    return {
        "type": "modal",
        "callback_id": "freeform_submit",
        "title": {"type": "plain_text", "text": "Request lunch"},
        "submit": {"type": "plain_text", "text": "Send"},
        "blocks": [
            {
                "type": "input",
                "block_id": "freeform_text",
                "label": {"type": "plain_text", "text": "What do you want?"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "text",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "e.g. that banh mi thing again, no coriander, enough for two days"},
                },
            },
            {
                "type": "input",
                "block_id": "freeform_half",
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
