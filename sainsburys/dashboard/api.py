import json
import os
import sys
import time

from flask import Flask, Response, jsonify, send_file, stream_with_context
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── Mock data (returned whenever the DB is unavailable) ──────────────────────

MOCK_STATS = {"saved_week": 47.30, "items_rescued": 12, "pending_orders": 1, "active_claimers": 7}

MOCK_LEADERBOARD = [
    {"slack_id": "U001", "name": "Alice Chen",   "saved": 18.50},
    {"slack_id": "U002", "name": "Bob Smith",    "saved": 12.30},
    {"slack_id": "U003", "name": "Carol Jones",  "saved":  9.80},
    {"slack_id": "U004", "name": "Dave Kumar",   "saved":  4.20},
    {"slack_id": "U005", "name": "Eve Williams", "saved":  2.50},
]

MOCK_RESCUE = [
    {"id": 1, "name": "Hummus & Flatbreads",    "days_left": 0, "qty_remaining": 2, "price": 2.50, "risk_score": 6.2},
    {"id": 2, "name": "Mixed Leaf Salad",       "days_left": 1, "qty_remaining": 3, "price": 1.80, "risk_score": 4.1},
    {"id": 3, "name": "Chicken Caesar Wrap",    "days_left": 2, "qty_remaining": 1, "price": 3.50, "risk_score": 2.5},
    {"id": 4, "name": "Fruit Pot",              "days_left": 2, "qty_remaining": 4, "price": 2.00, "risk_score": 2.3},
    {"id": 5, "name": "Falafel Bowl",           "days_left": 3, "qty_remaining": 2, "price": 4.50, "risk_score": 1.8},
    {"id": 6, "name": "Spiced Chickpea Wrap",   "days_left": 4, "qty_remaining": 5, "price": 3.50, "risk_score": 1.2},
]

MOCK_BASKET = {
    "week": "2026-07-20",
    "orders": [
        {
            "id": 1, "delivery_date": "2026-07-21", "status": "approved", "total": 87.40,
            "lines": [
                {"name": "Chicken Caesar Wrap", "qty": 8, "unit_price": 3.50},
                {"name": "Hummus & Flatbreads", "qty": 6, "unit_price": 2.50},
                {"name": "Mixed Leaf Salad",    "qty": 5, "unit_price": 1.80},
            ],
        },
        {
            "id": 2, "delivery_date": "2026-07-23", "status": "draft", "total": 62.20,
            "lines": [
                {"name": "Falafel Bowl",              "qty": 6, "unit_price": 4.50},
                {"name": "Fruit Pot",                 "qty": 8, "unit_price": 2.00},
                {"name": "Cheese & Chutney Baguette", "qty": 5, "unit_price": 3.20},
            ],
        },
    ],
}

MOCK_TOTALS = [
    {"week": "06-29", "claimed": 32.10, "wasted": 18.50},
    {"week": "07-06", "claimed": 41.20, "wasted": 12.30},
    {"week": "07-13", "claimed": 38.80, "wasted":  9.50},
    {"week": "07-20", "claimed": 47.30, "wasted":  5.20},
]

# Department Battle has no backing table in the schema — it is illustrative only,
# so it is served solely when mock is explicitly enabled.
MOCK_DEPARTMENTS = {"Engineering": 32.10, "Operations": 10.80, "Product": 4.40}

# Mock is OPT-IN. By default the dashboard shows real DB data (even when empty)
# and never substitutes fake data — so an empty/uninitialised DB looks empty, not
# populated. Set DASHBOARD_MOCK=1 for the wifi-down demo safety net.
ALLOW_MOCK = os.environ.get("DASHBOARD_MOCK", "0").lower() in ("1", "true", "yes")


# ── DB helper ─────────────────────────────────────────────────────────────────

def get_db():
    """Return a sqlite3 connection or None if the DB file is not reachable.

    Checks LUNCH_DB env var first (matches store.py convention), then
    falls back to the default relative path from the sainsburys package.
    """
    default = os.path.join(os.path.dirname(__file__), '..', 'data', 'lunch.db')
    path = os.environ.get("LUNCH_DB", default)
    if not os.path.exists(path):
        return None
    try:
        import sqlite3
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        return conn
    except Exception:
        return None


# ── Static ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_file(os.path.join(os.path.dirname(__file__), "index.html"))


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_file(os.path.join(os.path.dirname(__file__), "assets", filename))


# ── REST endpoints ────────────────────────────────────────────────────────────

EMPTY_STATS = {"saved_week": 0, "items_rescued": 0, "pending_orders": 0, "active_claimers": 0}


def _stats_fallback():
    """Served when there is no DB. Mock only if explicitly enabled, else zeros."""
    data = dict(MOCK_STATS if ALLOW_MOCK else EMPTY_STATS)
    data["live"] = False   # not real DB data
    return jsonify(data)


@app.route("/api/stats")
def stats():
    try:
        conn = get_db()
        if conn is None:
            return _stats_fallback()
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(value), 0) as saved
            FROM events
            WHERE kind = 'claimed'
              AND ts >= datetime('now', 'weekday 1', '-7 days')
        """)
        saved = float(cur.fetchone()[0])
        cur.execute("""
            SELECT COUNT(DISTINCT lot_id) FROM events
            WHERE kind = 'claimed'
              AND ts >= datetime('now', 'weekday 1', '-7 days')
        """)
        rescued = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'draft'")
        pending = int(cur.fetchone()[0])
        cur.execute("""
            SELECT COUNT(DISTINCT user_slack_id) FROM events
            WHERE kind = 'claimed'
              AND ts >= datetime('now', 'weekday 1', '-7 days')
        """)
        claimers = int(cur.fetchone()[0])
        conn.close()
        return jsonify({"saved_week": saved, "items_rescued": rescued,
                        "pending_orders": pending, "active_claimers": claimers,
                        "live": True})
    except Exception:
        return _stats_fallback()


@app.route("/api/leaderboard")
def leaderboard():
    try:
        conn = get_db()
        if conn is None:
            return jsonify(MOCK_LEADERBOARD if ALLOW_MOCK else [])
        cur = conn.cursor()
        cur.execute("""
            SELECT e.user_slack_id as slack_id,
                   COALESCE(u.name, e.user_slack_id) as name,
                   SUM(e.value) as saved
            FROM events e
            LEFT JOIN users u ON u.slack_id = e.user_slack_id
            WHERE e.kind = 'claimed'
            GROUP BY e.user_slack_id
            ORDER BY saved DESC
            LIMIT 10
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify(rows)
    except Exception:
        return jsonify(MOCK_LEADERBOARD if ALLOW_MOCK else [])


def _rescue_risk(i):
    """Deterministic expiry-risk score — mirrors flows.rescue._risk, inlined so
    /api/rescue never imports the Slack/agents chain (an unrelated import error
    there used to make this endpoint silently fall back to mock data)."""
    return (3.0 / (max(i["days_left"], 0) + 0.5)
            + 0.2 * float(i["price"])
            + 0.1 * float(i["qty_left"]))


@app.route("/api/rescue")
def rescue():
    # Selections-based model (no inventory lots): same source as /demo-rescue.
    # Reads store.leftovers() directly — store imports nothing heavy, so a real
    # (even empty) DB always yields real data, never mock.
    try:
        import store
    except Exception:
        return jsonify(MOCK_RESCUE if ALLOW_MOCK else [])
    try:
        items = sorted(store.leftovers(), key=_rescue_risk, reverse=True)
        return jsonify([
            {"id": i["product_id"], "name": i["name"], "days_left": i["days_left"],
             "qty_remaining": i["qty_left"], "price": i["price"],
             "risk_score": round(_rescue_risk(i), 2), "url": i.get("url")}
            for i in items
        ])
    except Exception:
        return jsonify(MOCK_RESCUE if ALLOW_MOCK else [])


@app.route("/api/departments")
def departments():
    # No department dimension exists in the schema, so there is no real data to
    # serve — the Department Battle is illustrative. Empty unless mock is on.
    return jsonify(MOCK_DEPARTMENTS if ALLOW_MOCK else {})


@app.route("/api/basket")
def basket():
    try:
        conn = get_db()
        if conn is None:
            return jsonify(MOCK_BASKET if ALLOW_MOCK else {"week": "", "orders": []})
        cur = conn.cursor()
        cur.execute("""
            SELECT id, week, delivery_date, status
            FROM orders
            WHERE week >= date('now', 'weekday 1', '-7 days')
            ORDER BY delivery_date
        """)
        orders = []
        for o in cur.fetchall():
            cur.execute("""
                SELECT p.name, ol.qty, ol.unit_price, p.url
                FROM order_lines ol
                JOIN products p ON p.id = ol.product_id
                WHERE ol.order_id = ?
            """, (o["id"],))
            lines = [dict(l) for l in cur.fetchall()]
            total = sum(l["qty"] * l["unit_price"] for l in lines)
            orders.append({
                "id": o["id"],
                "delivery_date": str(o["delivery_date"]),
                "status": o["status"],
                "total": total,
                "lines": lines,
            })
        conn.close()
        from datetime import date
        week = str(orders[0]["delivery_date"])[:10] if orders else str(date.today())
        return jsonify({"week": week, "orders": orders})
    except Exception:
        return jsonify(MOCK_BASKET if ALLOW_MOCK else {"week": "", "orders": []})


@app.route("/api/totals")
def totals():
    try:
        conn = get_db()
        if conn is None:
            return jsonify(MOCK_TOTALS if ALLOW_MOCK else [])
        cur = conn.cursor()
        cur.execute("""
            SELECT
                strftime('%m-%d', datetime(ts, 'weekday 1', '-7 days')) as week,
                SUM(CASE WHEN kind = 'claimed' THEN value ELSE 0 END) as claimed,
                SUM(CASE WHEN kind = 'wasted'  THEN value ELSE 0 END) as wasted
            FROM events
            GROUP BY week
            ORDER BY week DESC
            LIMIT 6
        """)
        rows = list(reversed([dict(r) for r in cur.fetchall()]))
        conn.close()
        return jsonify(rows)
    except Exception:
        return jsonify(MOCK_TOTALS if ALLOW_MOCK else [])


# ── SSE endpoint — live event stream ─────────────────────────────────────────

@app.route("/api/events/stream")
def events_stream():
    def generate():
        last_id = 0
        while True:
            try:
                conn = get_db()
                if conn:
                    cur = conn.cursor()
                    cur.execute(
                        """SELECT e.id, e.kind, e.value, e.user_slack_id,
                                  COALESCE(u.name, e.user_slack_id) AS user_name,
                                  p.name AS item
                           FROM events e
                           LEFT JOIN users u ON u.slack_id = e.user_slack_id
                           LEFT JOIN products p ON p.id = e.product_id
                           WHERE e.id > ? ORDER BY e.id LIMIT 20""",
                        (last_id,)
                    )
                    rows = cur.fetchall()
                    conn.close()
                    for row in rows:
                        last_id = row["id"]
                        payload = json.dumps({
                            "kind":  row["kind"],
                            "value": float(row["value"] or 0),
                            "user":  row["user_name"] or row["user_slack_id"],
                            "item":  row["item"] or "an item",
                        })
                        yield f"data: {payload}\n\n"
            except Exception:
                pass
            time.sleep(2)
            yield ": heartbeat\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", 3000))
    print(f"Dashboard running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
