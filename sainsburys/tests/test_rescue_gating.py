"""
Reproduces the bug: freshly ordered items land in the rescue bin BEFORE check-in.

Intended flow:  /order -> basket  ... /checkin ... -> ONLY THEN -> rescue bin.
A selection that has NOT been checked in must NOT appear in store.leftovers().

Run:  .venv/bin/python tests/test_rescue_gating.py
"""
import json
import os
import sys
import tempfile
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# Isolate the DB *before* importing store (store reads LUNCH_DB at import time).
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["LUNCH_DB"] = _tmp.name

import sqlite3

import store  # noqa: E402


def _fresh_db():
    with open(os.path.join(ROOT, "data", "schema_sqlite.sql")) as f:
        schema = f.read()
    conn = sqlite3.connect(_tmp.name)
    conn.executescript(schema)
    # one long-shelf-life product + two users
    conn.execute("insert into products (id, name, category, price, shelf_life_days) "
                 "values (1, 'Hummus Pot', 'dips', 1.50, 20)")
    conn.execute("insert into products (id, name, category, price, shelf_life_days) "
                 "values (2, 'Falafel Wrap', 'wraps', 3.00, 20)")
    conn.execute("insert into users (slack_id, name) values ('U1', 'Ada')")
    conn.execute("insert into users (slack_id, name) values ('U2', 'Ben')")
    conn.commit()
    conn.close()


def _order(user, week, pid, qty):
    store.record_selection(
        user, week, "early",
        parsed={"product_lines": [{"product_id": pid, "qty": qty}]},
    )


def _left(week):
    return {i["product_id"]: i["qty_left"] for i in store.leftovers(week)}


def main():
    _fresh_db()
    monday = date.today() - timedelta(days=date.today().weekday())

    # 1) Ada orders 2 hummus. No check-in yet -> should be in basket, NOT rescue.
    _order("U1", monday, pid=1, qty=2)
    left = _left(monday)
    assert 1 not in left, (
        "BUG: hummus is in the rescue bin before any check-in: %r" % left
    )

    # 2) Ada checks in "Some left" (0.5 of 2 = 1 eaten) -> 1 remaining now rescuable.
    store.record_consumption("U1", product_id=1, fraction=0.5, qty_ordered=2)
    left = _left(monday)
    assert abs(left.get(1, 0) - 1.0) < 1e-6, (
        "after check-in, expected 1 hummus left, got %r" % left
    )

    # 3) Second loop: Ben orders a falafel wrap, no check-in -> must NOT appear,
    #    even though other items are already on the board.
    _order("U2", monday, pid=2, qty=1)
    left = _left(monday)
    assert 2 not in left, (
        "BUG: freshly-ordered wrap hit the rescue bin before Ben checked in: %r" % left
    )
    assert abs(left.get(1, 0) - 1.0) < 1e-6, "Ada's rescued hummus should still be there"

    print("PASS: rescue bin is gated on check-in")


if __name__ == "__main__":
    try:
        main()
    finally:
        os.unlink(_tmp.name)
