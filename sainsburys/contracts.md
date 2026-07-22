# contracts.md — the shared interface between tracks A, B, and C

## store.py signatures

```python
record_selection(user, week, half, meal_id=None, parsed=None, freeform=None) -> Selection
confirm_selection(selection_id) -> None
build_baskets(week) -> list[Order]
approve_order(order_id) -> Order
deliver_order(order_id) -> list[Lot]
open_items_for(user, week) -> list[LotShare]
record_consumption(user, lot_id, fraction) -> Event
leftovers() -> list[Lot]
claim_lot(lot_id, user) -> Event          # .name, .value
sweep_waste(week) -> Digest
leaderboard() -> list
weekly_totals() -> list
```

## Button action_ids

| action_id        | value         | handler                  |
|------------------|---------------|--------------------------|
| meal_pick_early  | meal_id (str) | handlers.on_meal_pick_early |
| meal_pick_late   | meal_id (str) | handlers.on_meal_pick_late  |
| freeform_open    | —             | handlers.on_freeform_open   |
| approve_order    | order_id      | handlers.on_approve_order   |
| claim            | lot_id        | handlers.on_claim           |
| checkin_ate      | lot_id        | handlers.on_checkin_ate     |
| checkin_some     | lot_id        | handlers.on_checkin_some    |
| checkin_none     | lot_id        | handlers.on_checkin_none    |

## Modal callback_ids

| callback_id      | handler                    |
|------------------|----------------------------|
| freeform_submit  | handlers.on_freeform_submit |

## Rules
- Changing a store.py signature = tell the group first.
- No track writes SQL directly — all reads/writes go through store.py.
- `main` is always demoable. Merge at every checkpoint.
