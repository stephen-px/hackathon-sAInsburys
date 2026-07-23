"""
Map every catalogue product to its live sainsburys.co.uk identity
(product_uid + product page URL) via the search API, cached onto products.
Makes confirm-time trolley pushes instant and product links real.

No login needed — the search API answers anonymously.
Idempotent — only touches products with no sainsburys_uid yet.
    python data/backfill_sainsburys.py             # all unmapped (~5 min for 737)
    python data/backfill_sainsburys.py --limit 10  # smoke test
"""
import argparse
import csv
import os
import sys
import time
from pathlib import Path

os.environ["GROCERY_ANON"] = "1"  # never bulk-search on the real account
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # sainsburys/

import grocery
import store

CATALOGUE = Path(__file__).parent / "catalogue.csv"


def export_csv():
    """Write mapped url + sainsburys_uid back into catalogue.csv so the
    mapping survives any DB wipe/reseed and travels with the repo."""
    mapped = {p["name"]: p for p in store._q(
        "select name, url, sainsburys_uid from products where sainsburys_uid is not null",
        fetch="all") or []}
    with open(CATALOGUE, newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        hit = mapped.get(row["name"])
        if hit:
            row["url"] = hit["url"] or row.get("url") or ""
            row["sainsburys_uid"] = hit["sainsburys_uid"]
        else:
            row.setdefault("sainsburys_uid", "")
    with open(CATALOGUE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "category", "price",
                                               "shelf_life_days", "url", "sainsburys_uid"])
        writer.writeheader()
        writer.writerows(rows)
    print("Exported %d mappings to %s" % (len(mapped), CATALOGUE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=0.4, help="pause between searches")
    ap.add_argument("--export-only", action="store_true",
                    help="just write current DB mappings back to catalogue.csv")
    args = ap.parse_args()

    if args.export_only:
        export_csv()
        return

    todo = store.products_missing_sainsburys()
    if args.limit:
        todo = todo[: args.limit]
    print("Mapping %d products…" % len(todo))

    unmatched = []
    for i, product in enumerate(todo, 1):
        try:
            uid, url = grocery.resolve_product(product["name"])
        except Exception as e:
            unmatched.append((product["name"], str(e)[:80]))
            print("  [%d/%d] ⚠️ %s — %s" % (i, len(todo), product["name"], e))
            time.sleep(args.sleep)
            continue
        if uid:
            store.set_product_sainsburys(product["id"], uid, url)
            print("  [%d/%d] ✓ %s → %s" % (i, len(todo), product["name"], uid))
        else:
            unmatched.append((product["name"], "no search hit"))
            print("  [%d/%d] ✗ %s — no match" % (i, len(todo), product["name"]))
        time.sleep(args.sleep)

    print("\nDone: %d mapped, %d unmatched." % (len(todo) - len(unmatched), len(unmatched)))
    for name, reason in unmatched:
        print("  unmatched: %s (%s)" % (name, reason))
    export_csv()


if __name__ == "__main__":
    main()
