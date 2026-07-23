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
from contextlib import contextmanager
from pathlib import Path

DB_PATH = os.environ.get("LUNCH_DB", str(Path(__file__).parent / "data" / "lunch.db"))


def _conn():
    # 5s busy_timeout + WAL so the bot's writes and the dashboard's SSE reads
    # never deadlock (WAL lets readers run concurrently with a single writer).
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma journal_mode = wal")
    conn.execute("pragma busy_timeout = 5000")
    conn.execute("pragma foreign_keys = on")
    return conn


@contextmanager
def _tx():
    """Transaction scope: commit on success, roll back on error, ALWAYS close.

    sqlite3's own `with conn` manages the transaction but never closes the
    handle — a leaked open connection keeps holding locks, which is what
    deadlocked the bot against the dashboard's SSE reader.
    """
    conn = _conn()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _q(sql, params=(), fetch=None):
    with _tx() as conn:
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

def record_selection(user, week, half, meal_id=None, parsed=None, freeform=None, status="pending"):
    """Insert a selection row. Returns the Selection record.

    status='proposed' rows are agent suggestions awaiting Accept — they are
    invisible to check-in, baskets, and leftovers until accepted."""
    return _q(
        "insert into selections (week, half, user_slack_id, meal_id, freeform, parsed, status) "
        "values (?, ?, ?, ?, ?, ?, ?) "
        "returning id, week, half, user_slack_id, meal_id, freeform, parsed, status",
        (str(week), half, user, meal_id, freeform,
         json.dumps(parsed) if parsed else None, status),
        fetch="one",
    )


def accept_selection(selection_id):
    """Promote a proposed suggestion into a real (pending) selection."""
    _q("update selections set status = 'pending' where id = ? and status = 'proposed'",
       (selection_id,))


def confirm_selection(selection_id):
    """Mark a selection confirmed."""
    _q("update selections set status = 'confirmed' where id = ?", (selection_id,))


def void_selection(selection_id):
    """Mark a selection void (user hit Fix — a replacement is coming)."""
    _q("update selections set status = 'void' where id = ?", (selection_id,))


def get_selection(selection_id):
    return _q(
        "select id, week, half, user_slack_id, meal_id, freeform, parsed, status "
        "from selections where id = ?",
        (selection_id,),
        fetch="one",
    )


def update_selection_parsed(selection_id, parsed, status="pending"):
    """Attach a (re)parsed plan to an existing selection."""
    _q(
        "update selections set parsed = ?, status = ? where id = ?",
        (json.dumps(parsed), status, selection_id),
    )


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

def _selection_lines(week, half, conn):
    """Aggregate qty per product across the week's selections for one half.

    Reads on the caller's connection so it never opens a nested handle inside
    an in-flight write transaction (that self-deadlocks SQLite).
    """
    selections = conn.execute(
        "select meal_id, parsed from selections "
        "where week = ? and half = ? and status in ('pending', 'confirmed')",
        (str(week), half),
    ).fetchall()
    qty_by_product = {}
    for sel in selections:
        if sel["meal_id"]:
            lines = [dict(r) for r in conn.execute(
                "select product_id, qty from meal_products where meal_id = ?",
                (sel["meal_id"],),
            ).fetchall()]
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
    (early → Monday delivery, late → Wednesday). Only replaces a half's
    existing draft if there are actual selections for it — so demo-seeded
    orders are never silently deleted by a half-empty order run.
    Returns the orders that were created or already existed.
    """
    from datetime import date, timedelta
    monday = date.fromisoformat(str(week))
    orders = []
    with _tx() as conn:
        for half, delivery in (("early", monday), ("late", monday + timedelta(days=2))):
            qty_by_product = _selection_lines(week, half, conn)
            if not qty_by_product:
                # No new selections for this half — leave any existing draft alone
                existing = conn.execute(
                    "select id, week, delivery_date, status from orders "
                    "where week = ? and delivery_date = ? and status = 'draft'",
                    (str(week), str(delivery)),
                ).fetchone()
                if existing:
                    lines = conn.execute(
                        "select p.name, ol.qty, ol.unit_price "
                        "from order_lines ol join products p on p.id = ol.product_id "
                        "where ol.order_id = ?", (existing["id"],)
                    ).fetchall()
                    orders.append({
                        "id": existing["id"], "week": str(week),
                        "delivery_date": str(delivery), "status": "draft",
                        "lines": [dict(l) for l in lines],
                    })
                continue

            # We have selections — delete the stale draft for this half and rebuild
            stale = conn.execute(
                "select id from orders where week = ? and delivery_date = ? and status = 'draft'",
                (str(week), str(delivery)),
            ).fetchall()
            for row in stale:
                conn.execute("delete from order_lines where order_id = ?", (row["id"],))
                conn.execute("delete from orders where id = ?", (row["id"],))

            # Mark swept selections so re-running never double-counts them
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
        "select meal_id, parsed from selections "
        "where user_slack_id = ? and week = ? and status not in ('void', 'proposed')",
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


def record_consumption(user, product_id, fraction, qty_ordered=1.0):
    """
    Log a Friday check-in answer: 'consumed' event for fraction of the user's
    ordered quantity. fraction in [0, 1] (Ate=1, Some=0.5, None=0).
    Events are append-only; readers take the LATEST answer per user+product.
    Eating (and saying so) shrinks both the rescue board and your waste score.
    Returns {product_id, name, qty, value}.
    """
    product = _q(
        "select id, name, price from products where id = ?",
        (product_id,),
        fetch="one",
    )
    if not product:
        raise ValueError("unknown product %s" % product_id)
    qty = float(fraction) * float(qty_ordered)
    value = round(qty * product["price"], 2)
    _q(
        "insert into events (kind, user_slack_id, product_id, qty, value) "
        "values ('consumed', ?, ?, ?, ?)",
        (user, product_id, qty, value),
    )
    return {"product_id": product_id, "name": product["name"], "qty": qty, "value": value}


def user_week_summary(user, week):
    """£ ordered vs £ eaten (latest answer per product) — for the check-in wrap-up."""
    items = open_items_for(user, week)
    prices = {p["id"]: p["price"] for p in get_products_by_ids([i["product_id"] for i in items])}
    ordered_value = round(sum(i["qty"] * float(prices.get(i["product_id"], 0)) for i in items), 2)
    row = _q(
        "select sum(value) as eaten from ("
        "  select value, row_number() over (partition by product_id order by ts desc, id desc) as rn"
        "  from events where kind = 'consumed' and user_slack_id = ? and date(ts) >= ?"
        ") where rn = 1",
        (user, str(week)),
        fetch="one",
    )
    return {"ordered_value": ordered_value, "eaten_value": round(row["eaten"] or 0, 2)}


# ── Rescue board ──────────────────────────────────────────────────────────────

def leftovers(week=None):
    """
    What's left in the fridge, per product: everything ordered this week goes
    straight on the board (check-in was removed from the flow), minus any
    'consumed' events that may exist, minus 'claimed'/'wasted'. days_left is
    estimated from the half's delivery day (Mon/Wed) + the product's shelf life.
    Returns [{product_id, name, price, qty_left, days_left}].
    """
    from datetime import date, timedelta
    today = date.today()
    monday = date.fromisoformat(str(week)) if week else today - timedelta(days=today.weekday())

    # Ordered qty per (user, product), plus product metadata (min days_left across
    # halves). We track by user so we can gate each person's order on their check-in.
    ordered = {}   # (user_slack_id, pid) -> qty
    meta = {}      # pid -> {name, price, days_left}
    for half, delivered in (("early", monday), ("late", monday + timedelta(days=2))):
        selections = _q(
            "select user_slack_id, meal_id, parsed from selections "
            "where week = ? and half = ? and status not in ('void', 'proposed')",
            (str(monday), half),
            fetch="all",
        ) or []
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
                product = _q(
                    "select name, price, shelf_life_days from products where id = ?",
                    (pid,),
                    fetch="one",
                )
                if not product:
                    continue
                days_left = (delivered + timedelta(days=product["shelf_life_days"]) - today).days
                key = (sel["user_slack_id"], pid)
                ordered[key] = ordered.get(key, 0) + line["qty"]
                if pid in meta:
                    meta[pid]["days_left"] = min(meta[pid]["days_left"], days_left)
                else:
                    meta[pid] = {"name": product["name"], "price": product["price"],
                                 "days_left": days_left}

    # Consumed events (latest per user+product) still subtract if any exist,
    # but they are no longer a gate — ordered items are board-eligible at once.
    consumed = _q(
        "select user_slack_id, product_id, qty from ("
        "  select user_slack_id, product_id, qty, row_number() over ("
        "    partition by user_slack_id, product_id order by ts desc, id desc) as rn"
        "  from events where kind = 'consumed' and date(ts) >= ?"
        ") where rn = 1",
        (str(monday),),
        fetch="all",
    ) or []
    consumed_by = {(ev["user_slack_id"], ev["product_id"]): ev["qty"] for ev in consumed}

    out = {}
    for (user, pid), qty in ordered.items():
        left = qty - consumed_by.get((user, pid), 0)
        if pid in out:
            out[pid]["qty_left"] += left
        else:
            m = meta[pid]
            out[pid] = {"product_id": pid, "name": m["name"], "price": m["price"],
                        "qty_left": left, "days_left": m["days_left"]}

    # Claimed: every claim (or sweep) counts — each is food leaving the fridge. These
    # subtract from the product-level pool (anyone can claim what's on the board).
    claimed = _q(
        "select product_id, sum(qty) as q from events "
        "where kind in ('claimed', 'wasted') and date(ts) >= ? group by product_id",
        (str(monday),),
        fetch="all",
    ) or []
    for ev in claimed:
        if ev["product_id"] in out:
            out[ev["product_id"]]["qty_left"] = round(out[ev["product_id"]]["qty_left"] - ev["q"], 2)

    for item in out.values():
        item["qty_left"] = round(item["qty_left"], 2)
    return [item for item in out.values() if item["qty_left"] > 0.01]


def claim_product(product_id, user, qty=1.0):
    """
    One-tap claim: log a 'claimed' event. Defaults to one unit (the Slack
    one-tap behaviour); pass a larger qty (e.g. the whole remaining lot from the
    dashboard) to claim more in a single event. Never claims more than is left.
    Raises ValueError if nothing is left. Returns {name, value, qty_left}.
    """
    item = next((i for i in leftovers() if i["product_id"] == product_id), None)
    if not item:
        raise ValueError("nothing left of product %s" % product_id)
    qty = min(float(qty), item["qty_left"])
    value = round(qty * item["price"], 2)
    _q(
        "insert into events (kind, user_slack_id, product_id, qty, value) "
        "values ('claimed', ?, ?, ?, ?)",
        (user, product_id, qty, value),
    )
    return {"product_id": product_id, "name": item["name"], "value": value,
            "qty_left": round(item["qty_left"] - qty, 2)}


def claimed_total(week=None):
    """£ rescued from the bin this week — the running counter."""
    from datetime import date, timedelta
    today = date.today()
    monday = date.fromisoformat(str(week)) if week else today - timedelta(days=today.weekday())
    row = _q(
        "select sum(value) as total from events where kind = 'claimed' and date(ts) >= ?",
        (str(monday),),
        fetch="one",
    )
    return round(row["total"] or 0, 2)


# ── Digest / reporting ────────────────────────────────────────────────────────

def _ordered_by_user(week=None):
    """Ordered qty per (user, product) for the week + product meta. Shared by
    leftovers-style calculations and the waste sweep."""
    from datetime import date, timedelta
    today = date.today()
    monday = date.fromisoformat(str(week)) if week else today - timedelta(days=today.weekday())
    ordered, meta = {}, {}
    selections = _q(
        "select user_slack_id, meal_id, parsed from selections "
        "where week = ? and status not in ('void', 'proposed')",
        (str(monday),),
        fetch="all",
    ) or []
    for sel in selections:
        if sel["meal_id"]:
            lines = _q("select product_id, qty from meal_products where meal_id = ?",
                       (sel["meal_id"],), fetch="all") or []
        elif sel["parsed"]:
            lines = json.loads(sel["parsed"]).get("product_lines", [])
        else:
            continue
        for line in lines:
            pid = line["product_id"]
            if pid not in meta:
                product = _q("select name, price from products where id = ?", (pid,), fetch="one")
                if not product:
                    continue
                meta[pid] = {"name": product["name"], "price": product["price"]}
            key = (sel["user_slack_id"], pid)
            ordered[key] = ordered.get(key, 0) + line["qty"]
    return monday, ordered, meta


def sweep_waste(week=None):
    """
    End-of-week sweep (the /reset moment): everything ordered but not claimed
    is logged as 'wasted' — ATTRIBUTED to whoever ordered it, so wasters lose
    leaderboard points.

    Claims are product-level (anyone can rescue anyone's food), so each
    product's claimed qty reduces its orderers' waste proportionally.
    Returns {wasted_items, wasted_value, by_user: [{slack_id, name, wasted}]}.
    """
    monday, ordered, meta = _ordered_by_user(week)

    consumed = _q(
        "select user_slack_id, product_id, qty from ("
        "  select user_slack_id, product_id, qty, row_number() over ("
        "    partition by user_slack_id, product_id order by ts desc, id desc) as rn"
        "  from events where kind = 'consumed' and date(ts) >= ?"
        ") where rn = 1",
        (str(monday),),
        fetch="all",
    ) or []
    consumed_by = {(ev["user_slack_id"], ev["product_id"]): ev["qty"] for ev in consumed}

    removed = _q(  # already left the fridge: rescued or previously swept
        "select product_id, sum(qty) as q from events "
        "where kind in ('claimed', 'wasted') and date(ts) >= ? group by product_id",
        (str(monday),),
        fetch="all",
    ) or []
    removed_by_product = {ev["product_id"]: ev["q"] for ev in removed}

    # Per-user unconsumed, and per-product totals to prorate claims across users
    unconsumed = {k: max(0, qty - consumed_by.get(k, 0)) for k, qty in ordered.items()}
    total_unconsumed = {}
    for (user, pid), qty in unconsumed.items():
        total_unconsumed[pid] = total_unconsumed.get(pid, 0) + qty

    by_user, total_value, wasted_items = {}, 0.0, set()
    with _tx() as conn:
        for (user, pid), qty in unconsumed.items():
            if qty <= 0 or total_unconsumed[pid] <= 0:
                continue
            pool_left = max(0, total_unconsumed[pid] - removed_by_product.get(pid, 0))
            share = round(qty * pool_left / total_unconsumed[pid], 2)
            if share < 0.01:
                continue
            value = round(share * float(meta[pid]["price"]), 2)
            conn.execute(
                "insert into events (kind, user_slack_id, product_id, qty, value) "
                "values ('wasted', ?, ?, ?, ?)",
                (user, pid, share, value),
            )
            by_user[user] = round(by_user.get(user, 0) + value, 2)
            total_value += value
            wasted_items.add(pid)

    names = {u["slack_id"]: u["name"] for u in
             (_q("select slack_id, name from users", fetch="all") or [])}
    ranking = sorted(
        ({"slack_id": u, "name": names.get(u, u), "wasted": v} for u, v in by_user.items()),
        key=lambda r: r["wasted"], reverse=True,
    )
    return {"wasted_items": len(wasted_items), "wasted_value": round(total_value, 2),
            "by_user": ranking}


def wipe_orders():
    """The /reset wipe: clear all ordering state for a fresh week. Events (the
    score history), users, and the catalogue survive."""
    with _tx() as conn:
        conn.execute("delete from order_lines")
        conn.execute("delete from orders")
        conn.execute("delete from selections")


def leaderboard():
    """Net points: £ claimed (rescued) minus £ wasted. Wasting food costs you."""
    return _q("""
        SELECT e.user_slack_id as slack_id,
               COALESCE(u.name, e.user_slack_id) as name,
               ROUND(SUM(CASE WHEN e.kind = 'claimed' THEN e.value ELSE 0 END), 2) as claimed,
               ROUND(SUM(CASE WHEN e.kind = 'wasted'  THEN e.value ELSE 0 END), 2) as wasted,
               ROUND(SUM(CASE WHEN e.kind = 'claimed' THEN e.value
                             WHEN e.kind = 'wasted'  THEN -e.value ELSE 0 END), 2) as net
        FROM events e
        LEFT JOIN users u ON u.slack_id = e.user_slack_id
        WHERE e.kind IN ('claimed', 'wasted') AND e.user_slack_id IS NOT NULL
        GROUP BY e.user_slack_id
        ORDER BY net DESC LIMIT 10
    """, fetch="all") or []


def weekly_totals():
    rows = _q("""
        SELECT strftime('%m-%d', datetime(ts, 'weekday 1', '-7 days')) as week,
               SUM(CASE WHEN kind = 'claimed' THEN value ELSE 0 END) as claimed,
               SUM(CASE WHEN kind = 'wasted'  THEN value ELSE 0 END) as wasted
        FROM events
        GROUP BY week
        ORDER BY week DESC LIMIT 6
    """, fetch="all") or []
    return list(reversed(rows))
