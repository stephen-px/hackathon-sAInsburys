"""
Real Sainsbury's trolley integration — ADD TO BASKET ONLY.

Reads the browser session captured by vendor/uk-grocery-cli's Playwright login
(~/.sainsburys/session.json) and calls the same internal REST endpoints the
website uses. Deliberately implements nothing beyond search / add / read-basket:
no slot booking, no checkout, no ordering. A human reviews the filled trolley
on sainsburys.co.uk and takes it from there.

One-time setup (interactive, SMS 2FA):
    cd vendor/uk-grocery-cli && npm run groc login -- --email YOU --password PW
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

API_BASE = "https://www.sainsburys.co.uk/groceries-api/gol-services"
TROLLEY_URL = "https://www.sainsburys.co.uk/gol-ui/trolley"
SESSION_FILE = Path.home() / ".sainsburys" / "session.json"
STORE_NUMBER = os.environ.get("SAINSBURYS_STORE_NUMBER", "0560")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class NotConnected(Exception):
    """No usable Sainsbury's session — run the uk-grocery-cli login."""


def _load_session():
    if not SESSION_FILE.exists():
        raise NotConnected("no session file at %s" % SESSION_FILE)
    data = json.loads(SESSION_FILE.read_text())
    expires = data.get("expiresAt")
    if expires and datetime.fromisoformat(expires.replace("Z", "+00:00")) < datetime.now(timezone.utc):
        raise NotConnected("session expired — re-run the Sainsbury's login")
    return data


def _client(require_session=True):
    """HTTP client. Search works anonymously; basket writes need the real
    account session so the trolley shows up in the user's browser.

    GROCERY_ANON=1 forces anonymous requests even when a session exists —
    bulk jobs (the catalogue backfill) must never run on the real account."""
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    if os.environ.get("GROCERY_ANON") and not require_session:
        return s
    try:
        session_data = _load_session()
    except NotConnected:
        if require_session:
            raise
        return s
    cookies = session_data["cookies"]
    s.headers["Cookie"] = "; ".join("%s=%s" % (c["name"], c["value"]) for c in cookies)
    auth = next((c for c in cookies if c["name"].startswith("WC_AUTHENTICATION_")), None)
    if auth:
        s.headers["wcauthtoken"] = auth["value"]
    return s


def _pick_time():
    # The site sends a pick_time ~24h out on every basket call; mirror that.
    return (datetime.now(timezone.utc) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _basket_params():
    return {"pick_time": _pick_time(), "store_number": STORE_NUMBER, "slot_booked": "false"}


def is_connected():
    """True if a live session exists and the basket endpoint answers."""
    try:
        get_basket()
        return True
    except Exception:
        return False


def search(query, limit=8):
    """Search the live catalogue. Returns [{product_uid, name, price, url, in_stock}]."""
    resp = _client(require_session=False).get(
        API_BASE + "/product/v1/product",
        params={"filter[keyword]": query, "page_number": 1,
                "page_size": limit, "sort_order": "FAVOURITES_FIRST"},
        timeout=20,
    )
    resp.raise_for_status()
    out = []
    for p in resp.json().get("products", []):
        rp = p.get("retail_price") or {}
        url = p.get("full_url")
        if url and url.startswith("://"):  # API quirk: scheme-less full_url
            url = "https" + url
        elif url and url.startswith("/"):
            url = "https://www.sainsburys.co.uk" + url
        out.append({
            "product_uid": p.get("product_uid"),
            "name": p.get("name"),
            "price": rp.get("price") if isinstance(rp, dict) else rp,
            "url": url,
            "in_stock": p.get("in_stock") is not False and p.get("is_available") is not False,
        })
    return out


def add_to_basket(product_uid, qty):
    resp = _client().post(
        API_BASE + "/basket/v2/basket/item",
        params=_basket_params(),
        json={"product_uid": str(product_uid), "quantity": int(qty),
              "uom": "ea", "selected_catchweight": ""},
        timeout=20,
    )
    if resp.status_code >= 400:
        raise RuntimeError("add_to_basket %s x%s failed: %s %s"
                           % (product_uid, qty, resp.status_code, resp.text[:200]))


def get_basket():
    """Current trolley: {items: [...], item_count, total}."""
    resp = _client().get(API_BASE + "/basket/v2/basket",
                         params=_basket_params(), timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return {
        "items": [{
            "name": i.get("product", {}).get("name"),
            "quantity": i.get("quantity"),
            "subtotal": float(i.get("subtotal_price") or 0),
        } for i in data.get("items", [])],
        "item_count": data.get("item_count", 0),
        "total": float(data.get("total_price") or 0),
    }


import re

_STOP = {"sainsbury's", "sainsburys", "the", "taste", "difference", "so", "organic"}

# Spelling variants: catalogue names (from receipts) vs live site listings.
_ALIASES = {"hummus": "houmous", "humous": "houmous",
            "tortillas": "tortilla", "wholewheat": "wholemeal"}


def _name_tokens(name):
    # 2+ letters only: '300g'/'x10' otherwise leak 'g'/'x' as words and
    # let same-size products score as matches.
    words = re.findall(r"[a-z']{2,}", name.lower())
    return {_ALIASES.get(w, w) for w in words if w not in _STOP}


def _sizes(name):
    return set(re.findall(r"\d+(?:\.\d+)?\s?(?:g|kg|ml|l|pk|pack|x)", name.lower()))


def _word_overlap(query, hit_name):
    """Fraction of the query's words present in the hit (0..1)."""
    q, h = _name_tokens(query), _name_tokens(hit_name)
    return len(q & h) / len(q) if q else 0.0


def _match_score(query, hit_name):
    """Word overlap + 0.2 bonus for matching pack size (ranking only)."""
    score = _word_overlap(query, hit_name)
    if _sizes(query) & _sizes(hit_name):
        score += 0.2
    return score


def resolve_product(name, cached_uid=None):
    """Map a catalogue product name to a live product_uid.

    Ranks search hits by name similarity, but ACCEPTS only if a strict
    majority of the query's words appear in the hit — pack size never
    rescues a weak match ('Mini ... 6pk' once bought highlighter pens).
    Returns (product_uid, url), or (None, None): better to skip an item
    than put the wrong thing in a real trolley."""
    if cached_uid:
        return cached_uid, None
    hits = [h for h in search(name, limit=10) if h["product_uid"]]
    if not hits:
        return None, None
    scored = sorted(hits, key=lambda h: (_match_score(name, h["name"] or ""),
                                         h["in_stock"]), reverse=True)
    best = scored[0]
    if _word_overlap(name, best["name"] or "") <= 0.5:
        return None, None
    return best["product_uid"], best["url"]


def push_lines(lines):
    """Add order lines [{product_id, name, qty, sainsburys_uid?}] to the real trolley.

    Returns {added: [...], failed: [...], resolved: {product_id: (uid, url)}, total, trolley_url}.
    Never books a slot or checks out."""
    added, failed, resolved = [], [], {}
    for line in lines:
        name, qty = line["name"], int(line["qty"])
        try:
            uid, url = resolve_product(name, line.get("sainsburys_uid"))
            if not uid:
                failed.append({"name": name, "qty": qty, "reason": "no match on sainsburys.co.uk"})
                continue
            if not line.get("sainsburys_uid"):
                resolved[line["product_id"]] = (uid, url)
            add_to_basket(uid, qty)
            added.append({"name": name, "qty": qty})
        except Exception as e:
            failed.append({"name": name, "qty": qty, "reason": str(e)[:120]})
    try:
        total = get_basket()["total"]
    except Exception:
        total = None
    return {"added": added, "failed": failed, "resolved": resolved,
            "total": total, "trolley_url": TROLLEY_URL}
