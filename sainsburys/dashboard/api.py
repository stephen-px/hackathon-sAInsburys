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


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.route("/api/stats")
def stats():
    try:
        conn = get_db()
        if conn is None:
            return jsonify(MOCK_STATS)
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
                        "pending_orders": pending, "active_claimers": claimers})
    except Exception:
        return jsonify(MOCK_STATS)


@app.route("/api/leaderboard")
def leaderboard():
    try:
        conn = get_db()
        if conn is None:
            return jsonify(MOCK_LEADERBOARD)
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
        return jsonify(rows or MOCK_LEADERBOARD)
    except Exception:
        return jsonify(MOCK_LEADERBOARD)


@app.route("/api/rescue")
def rescue():
    try:
        conn = get_db()
        if conn is None:
            return jsonify(MOCK_RESCUE)
        cur = conn.cursor()
        cur.execute("""
            SELECT
                l.id,
                p.name,
                CAST(julianday(l.expiry_date) - julianday('now') AS INTEGER) as days_left,
                l.qty_remaining,
                p.price,
                3.0 / (MAX(CAST(julianday(l.expiry_date) - julianday('now') AS REAL), 0) + 0.5)
                    + 0.2 * p.price
                    + 0.1 * l.qty_remaining AS risk_score
            FROM inventory_lots l
            JOIN products p ON p.id = l.product_id
            WHERE l.qty_remaining > 0
            ORDER BY risk_score DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify(rows or MOCK_RESCUE)
    except Exception:
        return jsonify(MOCK_RESCUE)


@app.route("/api/basket")
def basket():
    try:
        conn = get_db()
        if conn is None:
            return jsonify(MOCK_BASKET)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, week, delivery_date, status
            FROM orders
            WHERE week >= datetime('now', 'weekday 1', '-7 days')
            ORDER BY delivery_date
        """)
        orders = []
        for o in cur.fetchall():
            cur.execute("""
                SELECT p.name, ol.qty, ol.unit_price
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
        week = str(orders[0]["delivery_date"])[:10] if orders else MOCK_BASKET["week"]
        return jsonify({"week": week, "orders": orders or MOCK_BASKET["orders"]})
    except Exception:
        return jsonify(MOCK_BASKET)


@app.route("/api/totals")
def totals():
    try:
        conn = get_db()
        if conn is None:
            return jsonify(MOCK_TOTALS)
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
        return jsonify(rows or MOCK_TOTALS)
    except Exception:
        return jsonify(MOCK_TOTALS)


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
                        "SELECT id, kind, value, user_slack_id FROM events WHERE id > ? ORDER BY id LIMIT 20",
                        (last_id,)
                    )
                    rows = cur.fetchall()
                    conn.close()
                    for row in rows:
                        last_id = row["id"]
                        payload = json.dumps({
                            "kind":  row["kind"],
                            "value": float(row["value"] or 0),
                            "user":  row["user_slack_id"],
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
