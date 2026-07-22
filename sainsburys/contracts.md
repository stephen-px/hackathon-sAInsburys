# contracts.md — the shared interface between tracks

## store.py signatures

```python
# Users
ensure_user(slack_id, name) -> None

# Selections
record_selection(user, week, half, meal_id=None, parsed=None, freeform=None) -> Selection
confirm_selection(selection_id) -> None

# Catalogue helpers (used by agent tools)
search_products_db(query) -> list[Product]
get_meals_db() -> list[Meal]
get_user_prefs_db(user_slack_id) -> dict
get_products_by_ids(ids) -> list[Product]

# Check-in (implemented — /demo-checkin)
# No delivery tracking: check-in works directly off each user's selections.
users_with_selections(week) -> list[slack_id]
open_items_for(user, week) -> list[{product_id, name, qty}]
record_consumption(user, product_id, fraction) -> {product_id, name, qty, value}

# Basket aggregation (implemented — future /demo-aggregate)
build_baskets(week) -> list[Order]        # Order includes "lines" [{product_id, name, qty, unit_price}]
approve_order(order_id) -> Order

# TODO — not yet implemented
leftovers() -> list[Lot]
claim_lot(lot_id, user) -> Event
sweep_waste(week) -> Digest
leaderboard() -> list
weekly_totals() -> list
```

## Slash commands

| command       | handler                | description              |
|---------------|------------------------|--------------------------|
| /order        | handlers.order         | Open the order modal     |
| /demo-checkin | handlers.demo_checkin  | Send Friday check-in DMs |

## Button action_ids

| action_id    | value      | handler                  |
|--------------|------------|--------------------------|
| checkin_ate  | product_id | handlers.on_checkin_ate  |
| checkin_some | product_id | handlers.on_checkin_some |
| checkin_none | product_id | handlers.on_checkin_none |

## Modal callback_ids

| callback_id  | handler                  |
|--------------|--------------------------|
| order_submit | handlers.on_order_submit |

## Rules
- Changing a store.py signature = tell the group first.
- No track writes SQL directly — all reads/writes go through store.py.
- `main` is always demoable. Merge at every checkpoint.
