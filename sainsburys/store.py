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

def search_products_db(query):
    like = "%{}%".format(query)
    return _q(
        "select id, name, category, price, shelf_life_days from products "
        "where name like ? or category like ? limit 15",
        (like, like),
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

def build_baskets(week):
    raise NotImplementedError


def approve_order(order_id):
    raise NotImplementedError


def deliver_order(order_id):
    raise NotImplementedError


# ── Check-in / consumption ────────────────────────────────────────────────────

def open_items_for(user, week):
    raise NotImplementedError


def record_consumption(user, lot_id, fraction):
    raise NotImplementedError


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
