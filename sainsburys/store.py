"""
Single source of truth for all DB reads/writes.
No agent or handler should ever touch SQL directly — call these functions.
See contracts.md for the full surface and payload shapes.
"""
import os
from datetime import date
import psycopg2
from psycopg2.extras import RealDictCursor, Json

DATABASE_URL = os.environ["DATABASE_URL"]


def _conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def _q(sql, params=(), fetch=None):
    conn = _conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if fetch == "one":
                    row = cur.fetchone()
                    return dict(row) if row else None
                if fetch == "all":
                    return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ── Users ──────────────────────────────────────────────────────────────────────

def ensure_user(slack_id: str, name: str):
    _q(
        "INSERT INTO users (slack_id, name) VALUES (%s, %s) "
        "ON CONFLICT (slack_id) DO UPDATE SET name = EXCLUDED.name",
        (slack_id, name),
    )


# ── Selections ────────────────────────────────────────────────────────────────

def record_selection(user, week, half, meal_id=None, parsed=None, freeform=None):
    """Insert a selection row. Returns the Selection record."""
    return _q(
        """INSERT INTO selections (week, half, user_slack_id, meal_id, freeform, parsed, status)
           VALUES (%s, %s, %s, %s, %s, %s, 'pending')
           RETURNING id, week, half, user_slack_id, meal_id, freeform, parsed, status""",
        (week, half, user, meal_id, freeform, Json(parsed) if parsed else None),
        fetch="one",
    )


def confirm_selection(selection_id):
    """Mark a selection confirmed."""
    _q("UPDATE selections SET status = 'confirmed' WHERE id = %s", (selection_id,))


# ── Catalogue helpers (used by agent tools) ───────────────────────────────────

def search_products_db(query: str) -> list:
    return _q(
        "SELECT id, name, category, price, shelf_life_days FROM products "
        "WHERE name ILIKE %s OR category ILIKE %s LIMIT 15",
        (f"%{query}%", f"%{query}%"),
        fetch="all",
    ) or []


def get_meals_db() -> list:
    return _q(
        """SELECT m.id, m.name, m.description, m.tags,
                  json_agg(json_build_object(
                      'product_id', mp.product_id,
                      'qty', mp.qty,
                      'product_name', p.name
                  )) AS products
           FROM meals m
           LEFT JOIN meal_products mp ON mp.meal_id = m.id
           LEFT JOIN products p ON p.id = mp.product_id
           GROUP BY m.id""",
        fetch="all",
    ) or []


def get_user_prefs_db(user_slack_id: str) -> dict:
    row = _q(
        "SELECT slack_id, dietary, taste FROM users WHERE slack_id = %s",
        (user_slack_id,),
        fetch="one",
    )
    return row or {"slack_id": user_slack_id, "dietary": [], "taste": {}}


def get_products_by_ids(ids: list) -> list:
    if not ids:
        return []
    return _q(
        "SELECT id, name, price FROM products WHERE id = ANY(%s)",
        (ids,),
        fetch="all",
    ) or []


# ── Orders / baskets ──────────────────────────────────────────────────────────

def build_baskets(week) -> list:
    raise NotImplementedError


def approve_order(order_id):
    raise NotImplementedError


def deliver_order(order_id) -> list:
    raise NotImplementedError


# ── Check-in / consumption ────────────────────────────────────────────────────

def open_items_for(user, week) -> list:
    raise NotImplementedError


def record_consumption(user, lot_id, fraction) -> dict:
    raise NotImplementedError


# ── Rescue board ──────────────────────────────────────────────────────────────

def leftovers() -> list:
    raise NotImplementedError


def claim_lot(lot_id, user) -> dict:
    raise NotImplementedError


# ── Digest / reporting ────────────────────────────────────────────────────────

def sweep_waste(week) -> dict:
    raise NotImplementedError


def leaderboard() -> list:
    raise NotImplementedError


def weekly_totals() -> list:
    raise NotImplementedError
