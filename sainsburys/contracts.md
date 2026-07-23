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

# Check-in (implemented — /demo-checkin)
# No delivery tracking: check-in works directly off each user's selections.
users_with_selections(week) -> list[slack_id]
open_items_for(user, week) -> list[{product_id, name, qty}]
record_consumption(user, product_id, fraction) -> {product_id, name, qty, value}

# Basket aggregation (implemented — future /demo-aggregate)
build_baskets(week) -> list[Order]        # Order includes "lines" [{product_id, name, qty, unit_price, url}]
approve_order(order_id) -> Order
order_lines(order_id) -> list[{product_id, name, qty, unit_price, sainsburys_uid, url}]

# Real Sainsbury's mapping (products.sainsburys_uid / products.url)
products_missing_sainsburys() -> list[{id, name}]
set_product_sainsburys(product_id, uid, url=None) -> None

# Rescue board (implemented — /demo-rescue; product-keyed, no lots)
leftovers(week=None) -> list[{product_id, name, price, qty_left, days_left, url}]
claim_product(product_id, user) -> {product_id, name, value, qty_left}

# TODO — not yet implemented
sweep_waste(week) -> Digest
leaderboard() -> list
weekly_totals() -> list
```

## Slash commands

| command       | handler                | description              |
|---------------|------------------------|--------------------------|
| /order        | handlers.order         | Open the order modal     |
| /suggest      | handlers.suggest       | Suggest a lunch (accept/refine loop) |
| /demo-checkin | handlers.demo_checkin  | Send Friday check-in DMs |
| /demo-rescue  | handlers.demo_rescue   | Post the rescue board    |

## Button action_ids

| action_id    | value      | handler                  |
|--------------|------------|--------------------------|
| checkin_ate  | product_id | handlers.on_checkin_ate  |
| checkin_some | product_id | handlers.on_checkin_some |
| checkin_none | product_id | handlers.on_checkin_none |
| claim        | product_id | handlers.on_claim        |

## Modal callback_ids

| callback_id  | handler                  |
|--------------|--------------------------|
| order_submit | handlers.on_order_submit |

## grocery.py — real sainsburys.co.uk integration (ADD TO BASKET ONLY)

```python
# Session comes from a one-time Playwright login (vendor/uk-grocery-cli —
# not committed; clone + install it once per machine):
#   git clone https://github.com/abracadabra50/uk-grocery-cli vendor/uk-grocery-cli
#   cd vendor/uk-grocery-cli && npm install && npx playwright install chromium
#   npm run groc login -- --email YOU --password PW
#   → saves ~/.sainsburys/session.json (SMS 2FA prompt in terminal)
# Saved to ~/.sainsburys/session.json. Search works anonymously; basket
# writes need the session. NO slot booking / checkout code exists.
grocery.search(query, limit=8) -> list[{product_uid, name, price, url, in_stock}]
grocery.add_to_basket(product_uid, qty) -> None
grocery.get_basket() -> {items, item_count, total}
grocery.is_connected() -> bool
grocery.push_lines(lines) -> {added, failed, resolved, total, trolley_url}

# Orchestration (flows/basket.py):
push_to_trolley(order_id) -> result      # called on Approve; caches resolved uids
trolley_summary_text(result) -> str      # Slack mrkdwn summary

# Product identity cache: data/backfill_sainsburys.py maps all catalogue
# products to real uids/urls (anonymous search) and writes them back into
# catalogue.csv so /demo-reset and re-seeds keep them.
```

## Rules
- Changing a store.py signature = tell the group first.
- No track writes SQL directly — all reads/writes go through store.py.
- `main` is always demoable. Merge at every checkpoint.
