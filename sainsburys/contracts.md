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

# TODO — not yet implemented
build_baskets(week) -> list[Order]
approve_order(order_id) -> Order
deliver_order(order_id) -> list[Lot]
open_items_for(user, week) -> list[LotShare]
record_consumption(user, lot_id, fraction) -> Event
leftovers() -> list[Lot]
claim_lot(lot_id, user) -> Event
sweep_waste(week) -> Digest
leaderboard() -> list
weekly_totals() -> list
```

## Slash commands

| command  | handler                  | description          |
|----------|--------------------------|----------------------|
| /order   | handlers.order           | Open the order modal |

## Modal callback_ids

| callback_id  | handler                  |
|--------------|--------------------------|
| order_submit | handlers.on_order_submit |

## Rules
- Changing a store.py signature = tell the group first.
- No track writes SQL directly — all reads/writes go through store.py.
- `main` is always demoable. Merge at every checkpoint.
