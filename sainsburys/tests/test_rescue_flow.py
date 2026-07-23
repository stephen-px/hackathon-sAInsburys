"""
Rescue flow, post-check-in-removal: ordered items go straight on the board,
claims subtract, and /reset attributes waste to the orderers (claims prorated).

Run:  .venv/bin/python tests/test_rescue_flow.py
"""
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

    # 1) Ordered items are board-eligible immediately (no check-in step).
    _order("U1", monday, pid=1, qty=2)   # Ada: 2 hummus (£1.50 each)
    _order("U2", monday, pid=1, qty=2)   # Ben: 2 hummus
    _order("U2", monday, pid=2, qty=1)   # Ben: 1 wrap (£3.00)
    left = _left(monday)
    assert abs(left.get(1, 0) - 4.0) < 1e-6, "expected 4 hummus on the board: %r" % left
    assert abs(left.get(2, 0) - 1.0) < 1e-6, "expected 1 wrap on the board: %r" % left

    # 2) A proposal (not yet accepted) must NOT hit the board.
    store.record_selection("U1", monday, "early", status="proposed",
                           parsed={"product_lines": [{"product_id": 2, "qty": 5}]})
    assert abs(_left(monday).get(2, 0) - 1.0) < 1e-6, "proposed rows leaked onto the board"

    # 3) Check-in answers subtract from the board (no gate — just reduction).
    #    Ada says "Some left" on her 2 hummus -> ate 1 -> board drops 4 -> 3.
    store.record_consumption("U1", product_id=1, fraction=0.5, qty_ordered=2)
    assert abs(_left(monday).get(1, 0) - 3.0) < 1e-6, "check-in didn't reduce the board"

    # 4) Claims subtract from the pool.
    store.claim_product(1, "U2", qty=2)  # Ben rescues 2 hummus (£3.00 claimed)
    assert abs(_left(monday).get(1, 0) - 1.0) < 1e-6, "claim didn't subtract"

    # 5) /reset sweep: hummus pool = Ada 1 + Ben 2 unconsumed, 1 left after claims
    #    -> waste prorated by share (Ada ⅓, Ben ⅔); Ben also bins his £3 wrap.
    digest = store.sweep_waste(monday)
    assert digest["wasted_items"] == 2, digest
    assert abs(digest["wasted_value"] - 4.50) < 0.05, digest
    by = {w["slack_id"]: w["wasted"] for w in digest["by_user"]}
    assert abs(by["U1"] - 0.50) < 0.02, by     # Ada: ⅓ of the leftover hummus
    assert abs(by["U2"] - 4.00) < 0.02, by     # Ben: ⅔ hummus + the wrap
    assert digest["by_user"][0]["slack_id"] == "U2", "Ben should top the wall of shame"

    # 6) Net leaderboard: Ben claimed £3.00, wasted £4.00 -> net -1.00; Ada -0.50.
    board = {r["slack_id"]: r for r in store.leaderboard()}
    assert abs(board["U2"]["net"] - (-1.00)) < 0.02, board
    assert abs(board["U1"]["net"] - (-0.50)) < 0.02, board

    # 7) Wipe clears orders but keeps the score history.
    store.wipe_orders()
    conn = sqlite3.connect(_tmp.name)
    sels, evs = conn.execute(
        "select (select count(*) from selections), (select count(*) from events)"
    ).fetchone()
    conn.close()
    assert sels == 0 and evs > 0, (sels, evs)
    assert _left(monday) == {}, "board should be empty after reset"

    print("PASS: board-on-order, claim subtraction, attributed waste, net leaderboard, reset wipe")


if __name__ == "__main__":
    try:
        main()
    finally:
        os.unlink(_tmp.name)
