import store
from agents import parser as parser_agent
from datetime import date, timedelta


def _current_week():
    today = date.today()
    return today - timedelta(days=today.weekday())


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

    try:
        result = parser_agent.parse(user_id, order_text, half)
        store.record_selection(user_id, week, half, freeform=order_text, parsed=result)

        product_ids = [line["product_id"] for line in result.get("product_lines", [])]
        products = {p["id"]: p for p in store.get_products_by_ids(product_ids)}

        lines_text = "\n".join(
            f"• {line['qty']}x *{products.get(line['product_id'], {}).get('name', f'Product {line[\"product_id\"]}')}"
            f"* — £{float(products.get(line['product_id'], {}).get('price', 0)) * float(line['qty']):.2f}"
            for line in result.get("product_lines", [])
        )
        notes = f"\n_Note: {result['notes']}_" if result.get("notes") else ""

        client.chat_postMessage(
            channel=dm_channel,
            text=(
                f":white_check_mark: *Order logged for {half} week!*\n"
                f"{lines_text}{notes}\n\n"
                f'_Your request: "{order_text}"_'
            ),
        )

    except Exception as e:
        store.record_selection(user_id, week, half, freeform=order_text)
        client.chat_postMessage(
            channel=dm_channel,
            text=(
                f":warning: Couldn't parse your order automatically, but I saved your request:\n"
                f"> {order_text}\n"
                f"_Error: {type(e).__name__}: {e}_"
            ),
        )
