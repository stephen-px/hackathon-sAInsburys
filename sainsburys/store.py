"""
Single source of truth for all DB reads/writes.
No agent or handler should ever touch SQL directly — call these functions.
See contracts.md for the full surface and payload shapes.
"""
import os
from dataclasses import dataclass
from datetime import date
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ["DATABASE_URL"]


def _conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


# ── Selections ────────────────────────────────────────────────────────────────

def record_selection(user, week, half, meal_id=None, parsed=None, freeform=None):
    """Insert or upsert a selection row. Returns the Selection record."""
    raise NotImplementedError


def confirm_selection(selection_id):
    """Mark a selection confirmed (after user reviews freeform parse)."""
    raise NotImplementedError


# ── Orders / baskets ──────────────────────────────────────────────────────────

def build_baskets(week) -> list:
    """Deterministic aggregation of confirmed selections into two draft Orders."""
    raise NotImplementedError


def approve_order(order_id):
    """Transition order from draft → approved. Returns Order."""
    raise NotImplementedError


def deliver_order(order_id) -> list:
    """Create inventory_lots from an approved order. Returns list[Lot]."""
    raise NotImplementedError


# ── Check-in / consumption ────────────────────────────────────────────────────

def open_items_for(user, week) -> list:
    """Return the lots associated with a user's selections for the week."""
    raise NotImplementedError


def record_consumption(user, lot_id, fraction) -> dict:
    """Decrement lot FIFO and insert a 'consumed' event. fraction in [0,1]."""
    raise NotImplementedError


# ── Rescue board ──────────────────────────────────────────────────────────────

def leftovers() -> list:
    """Return all lots with qty_remaining > 0, risk-scored, from the view."""
    raise NotImplementedError


def claim_lot(lot_id, user) -> dict:
    """Transactional: decrement lot, insert 'claimed' event. Returns Event with .name and .value."""
    raise NotImplementedError


# ── Digest / reporting ────────────────────────────────────────────────────────

def sweep_waste(week) -> dict:
    """Log remaining expired quantities as 'wasted' events. Returns Digest summary."""
    raise NotImplementedError


def leaderboard() -> list:
    raise NotImplementedError


def weekly_totals() -> list:
    raise NotImplementedError
