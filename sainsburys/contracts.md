# contracts.md — the shared interface between tracks

## store.py signatures

```python
# Users
ensure_user(slack_id, name) -> None

# Selections
# status lifecycle: proposed (suggestion awaiting Accept) → pending → confirmed / ordered; void = superseded
record_selection(user, week, half, meal_id=None, parsed=None, freeform=None, status='pending') -> Selection
confirm_selection(selection_id) -> None
accept_selection(selection_id) -> None    # proposed → pending
void_selection(selection_id) -> None
get_selection(selection_id) -> Selection
update_selection_parsed(selection_id, parsed, status='pending') -> None

# Catalogue helpers (used by agent tools)
search_products_db(query) -> list[Product]
get_meals_db() -> list[Meal]
get_user_prefs_db(user_slack_id) -> dict
get_products_by_ids(ids) -> list[Product]

# Check-in (implemented — /demo-checkin; answers shrink the board + waste score, no gate)
users_with_selections(week) -> list[slack_id]
open_items_for(user, week) -> list[{product_id, name, qty}]
record_consumption(user, product_id, fraction, qty_ordered=1.0) -> {product_id, name, qty, value}
user_week_summary(user, week) -> {ordered_value, eaten_value}

# Basket aggregation (rebuilt automatically when a plan is accepted; feeds the dashboard)
build_baskets(week) -> list[Order]        # Order includes "lines" [{product_id, name, qty, unit_price}]

# Rescue board (implemented — /demo-rescue; product-keyed, no lots, no check-in gate:
# everything ordered this week is board-eligible immediately)
leftovers(week=None) -> list[{product_id, name, price, qty_left, days_left}]
claim_product(product_id, user) -> {product_id, name, value, qty_left}

# Sweep / reset / scoring (implemented — /reset)
sweep_waste(week=None) -> {wasted_items, wasted_value, by_user}  # waste attributed to orderers, claims prorated
wipe_orders() -> None                    # clears selections/orders; events history survives
leaderboard() -> [{slack_id, name, claimed, wasted, net}]  # net = claimed − wasted, desc
weekly_totals() -> list
```

## Slash commands

| command       | handler                | description              |
|---------------|------------------------|--------------------------|
| /order        | handlers.order         | Unified flow: parse OR suggest → propose → Accept/Refine |
| /suggest      | handlers.suggest       | Alias of /order          |
| /demo-checkin | handlers.demo_checkin  | Send Friday check-in DMs |
| /demo-rescue  | handlers.demo_rescue   | Post the rescue board    |
| /reset        | handlers.reset         | Sweep waste (scored) + wipe orders + leaderboard |

## Button action_ids

| action_id         | value           | handler                       |
|-------------------|-----------------|-------------------------------|
| suggestion_accept | selection_id    | handlers.on_suggestion_accept |
| suggestion_refine | selection_id    | handlers.on_suggestion_refine |
| order_retry       | selection_id    | handlers.on_order_retry       |
| checkin_ate       | product_id:qty  | handlers.on_checkin_ate       |
| checkin_some      | product_id:qty  | handlers.on_checkin_some      |
| checkin_none      | product_id:qty  | handlers.on_checkin_none      |
| claim             | product_id      | handlers.on_claim             |

## Modal callback_ids

| callback_id  | handler                  |
|--------------|--------------------------|
| order_submit | handlers.on_order_submit |

## Rules
- Changing a store.py signature = tell the group first.
- No track writes SQL directly — all reads/writes go through store.py.
- `main` is always demoable. Merge at every checkpoint.
