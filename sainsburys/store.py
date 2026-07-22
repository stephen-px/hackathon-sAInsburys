"""
Single source of truth for all DB reads/writes.
No agent or handler should ever touch SQL directly — call these functions.
See contracts.md for the full surface and payload shapes.

Backend: SQLite (sainsburys/data/lunch.db). Public signatures are backend-agnostic —
swapping to Postgres/Supabase later only changes this file's internals.
"""
import json
import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("LUNCH_DB", str(Path(__file__).parent / "data" / "lunch.db"))


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn


def _q(sql, params=(), fetch=None):
    with _conn() as conn:
        cur = conn.execute(sql, params)
        if fetch == "one":
            row = cur.fetchone()
            return dict(row) if row else None
        if fetch == "all":
            return [dict(r) for r in cur.fetchall()]


# ── Users ──────────────────────────────────────────────────────────────────────

def ensure_user(slack_id, name):
    _q(
        "insert into users (slack_id, name) values (?, ?) "
        "on conflict (slack_id) do update set name = excluded.name",
        (slack_id, name),
    )


# ── Selections ────────────────────────────────────────────────────────────────

def record_selection(user, week, half, meal_id=None, parsed=None, freeform=None):
    """Insert a selection row. Returns the Selection record."""
    return _q(
        "insert into selections (week, half, user_slack_id, meal_id, freeform, parsed, status) "
        "values (?, ?, ?, ?, ?, ?, 'pending') "
        "returning id, week, half, user_slack_id, meal_id, freeform, parsed, status",
        (str(week), half, user, meal_id, freeform, json.dumps(parsed) if parsed else None),
        fetch="one",
    )


def confirm_selection(selection_id):
    """Mark a selection confirmed."""
    _q("update selections set status = 'confirmed' where id = ?", (selection_id,))


# ── Catalogue helpers (used by agent tools) ───────────────────────────────────

_STOPWORDS = {"a", "an", "the", "some", "of", "with", "and", "or", "for", "please"}


def _stem(token):
    # crude singular/plural + suffix normaliser so 'strawberry' matches 'Strawberries'
    for suffix in ("ies", "es", "s", "y"):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def search_products_db(query):
    tokens = [_stem(t) for t in query.lower().split() if t not in _STOPWORDS]
    if not tokens:
        return []
    # rank rows by how many query tokens they match; return any-match, best first
    score = " + ".join(
        "(case when lower(name) like ? or lower(category) like ? then 1 else 0 end)"
        for _ in tokens
    )
    where = " or ".join("lower(name) like ? or lower(category) like ?" for _ in tokens)
    likes = []
    for t in tokens:
        likes += ["%{}%".format(t), "%{}%".format(t)]
    return _q(
        "select id, name, category, price, shelf_life_days, ({score}) as hits "
        "from products where {where} order by hits desc, price asc limit 15".format(score=score, where=where),
        tuple(likes + likes),
        fetch="all",
    ) or []


def get_meals_db():
    meals = _q("select id, name, description, tags from meals", fetch="all") or []
    for meal in meals:
        meal["tags"] = json.loads(meal["tags"] or "[]")
        meal["products"] = _q(
            "select mp.product_id, mp.qty, p.name as product_name "
            "from meal_products mp join products p on p.id = mp.product_id "
            "where mp.meal_id = ?",
            (meal["id"],),
            fetch="all",
        ) or []
    return meals


def get_user_prefs_db(user_slack_id):
    row = _q(
        "select slack_id, dietary, taste from users where slack_id = ?",
        (user_slack_id,),
        fetch="one",
    )
    if not row:
        return {"slack_id": user_slack_id, "dietary": [], "taste": {}}
    row["dietary"] = json.loads(row["dietary"] or "[]")
    row["taste"] = json.loads(row["taste"] or "{}")
    return row


def get_products_by_ids(ids):
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    return _q(
        "select id, name, price from products where id in (%s)" % placeholders,
        tuple(ids),
        fetch="all",
    ) or []


# ── Orders / baskets ──────────────────────────────────────────────────────────

def _selection_lines(week, half):
    """Aggregate qty per product across the week's selections for one half."""
    selections = _q(
        "select meal_id, parsed from selections "
        "where week = ? and half = ? and status in ('pending', 'confirmed')",
        (str(week), half),
        fetch="all",
    ) or []
    qty_by_product = {}
    for sel in selections:
        if sel["meal_id"]:
            lines = _q(
                "select product_id, qty from meal_products where meal_id = ?",
                (sel["meal_id"],),
                fetch="all",
            ) or []
        elif sel["parsed"]:
            lines = json.loads(sel["parsed"]).get("product_lines", [])
        else:
            continue
        for line in lines:
            pid = line["product_id"]
            qty_by_product[pid] = qty_by_product.get(pid, 0) + line["qty"]
    return qty_by_product


def build_baskets(week):
    """
    Deterministic aggregation: this week's selections → two draft orders
    (early → Monday delivery, late → Wednesday). Re-running replaces any
    existing draft orders for the week. Returns orders with a "lines" list.
    """
    from datetime import date, timedelta
    monday = date.fromisoformat(str(week))
    orders = []
    with _conn() as conn:
        stale = conn.execute(
            "select id from orders where week = ? and status = 'draft'", (str(week),)
        ).fetchall()
        for row in stale:
            conn.execute("delete from order_lines where order_id = ?", (row["id"],))
            conn.execute("delete from orders where id = ?", (row["id"],))

        for half, delivery in (("early", monday), ("late", monday + timedelta(days=2))):
            qty_by_product = _selection_lines(week, half)
            if not qty_by_product:
                continue
            # Mark swept selections 'ordered' so re-running never double-counts them
            conn.execute(
                "update selections set status = 'ordered' "
                "where week = ? and half = ? and status in ('pending', 'confirmed')",
                (str(week), half),
            )
            cur = conn.execute(
                "insert into orders (week, delivery_date, status) values (?, ?, 'draft') returning id",
                (str(week), str(delivery)),
            )
            order_id = cur.fetchone()["id"]
            lines = []
            for pid, qty in qty_by_product.items():
                product = conn.execute(
                    "select name, price from products where id = ?", (pid,)
                ).fetchone()
                conn.execute(
                    "insert into order_lines (order_id, product_id, qty, unit_price) values (?, ?, ?, ?)",
                    (order_id, pid, qty, product["price"]),
                )
                lines.append({"product_id": pid, "name": product["name"],
                              "qty": qty, "unit_price": product["price"]})
            orders.append({"id": order_id, "week": str(week), "delivery_date": str(delivery),
                           "status": "draft", "lines": lines})
    return orders


def approve_order(order_id):
    """Transition draft → approved. Returns the Order."""
    order = _q(
        "update orders set status = 'approved' where id = ? and status = 'draft' "
        "returning id, week, delivery_date, status",
        (order_id,),
        fetch="one",
    )
    if not order:
        raise ValueError("order %s not found or not a draft" % order_id)
    return order


# ── Check-in / consumption ────────────────────────────────────────────────────

def users_with_selections(week):
    """Slack ids of everyone with a selection this week (who to DM for check-in)."""
    rows = _q(
        "select distinct user_slack_id from selections where week = ?",
        (str(week),),
        fetch="all",
    ) or []
    return [r["user_slack_id"] for r in rows]


def open_items_for(user, week):
    """
    What the user ordered this week, straight from their selections
    (meal picks expanded to products, freeform via the parsed plan).
    Returns [{product_id, name, qty}] — the list the check-in DM shows.
    """
    selections = _q(
        "select meal_id, parsed from selections where user_slack_id = ? and week = ?",
        (user, str(week)),
        fetch="all",
    ) or []

    qty_by_product = {}
    for sel in selections:
        if sel["meal_id"]:
            lines = _q(
                "select product_id, qty from meal_products where meal_id = ?",
                (sel["meal_id"],),
                fetch="all",
            ) or []
        elif sel["parsed"]:
            lines = json.loads(sel["parsed"]).get("product_lines", [])
        else:
            continue
        for line in lines:
            pid = line["product_id"]
            qty_by_product[pid] = qty_by_product.get(pid, 0) + line["qty"]

    items = []
    for pid, qty in qty_by_product.items():
        product = _q("select id, name from products where id = ?", (pid,), fetch="one")
        if product:
            items.append({"product_id": pid, "name": product["name"], "qty": qty})
    return items


def record_consumption(user, product_id, fraction):
    """
    Log a Friday check-in answer: 'consumed' event for fraction of one
    unit-as-sold of the product. fraction in [0, 1] (Ate=1, Some=0.5, None=0).
    Returns {product_id, name, qty, value}.
    """
    product = _q(
        "select id, name, price from products where id = ?",
        (product_id,),
        fetch="one",
    )
    if not product:
        raise ValueError("unknown product %s" % product_id)
    qty = float(fraction)
    value = round(qty * product["price"], 2)
    _q(
        "insert into events (kind, user_slack_id, product_id, qty, value) "
        "values ('consumed', ?, ?, ?, ?)",
        (user, product_id, qty, value),
    )
    return {"product_id": product_id, "name": product["name"], "qty": qty, "value": value}


# ── Rescue board ──────────────────────────────────────────────────────────────

def leftovers():
    raise NotImplementedError


def claim_lot(lot_id, user):
    raise NotImplementedError


# ── Digest / reporting ────────────────────────────────────────────────────────

def sweep_waste(week):
    raise NotImplementedError


def leaderboard():
    raise NotImplementedError


def weekly_totals():
    raise NotImplementedError
