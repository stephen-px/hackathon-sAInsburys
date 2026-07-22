from flows import basket


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
