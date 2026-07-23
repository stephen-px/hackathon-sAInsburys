"""
Dashboard names bug: anyone who only tapped buttons (claim / check-in) never
got a row in `users`, so the dashboard's COALESCE(u.name, e.user_slack_id)
showed their raw U… ID. identity.ensure_user_name resolves names via
users_info on every event-writing interaction, and backfill_missing_names
heals rows recorded before the fix.

Run:  .venv/bin/python tests/test_identity.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# Isolate the DB *before* importing store (store reads LUNCH_DB at import time).
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["LUNCH_DB"] = _tmp.name

import sqlite3

import identity  # noqa: E402
import store  # noqa: E402


def _fresh_db():
    with open(os.path.join(ROOT, "data", "schema_sqlite.sql")) as f:
        schema = f.read()
    conn = sqlite3.connect(_tmp.name)
    conn.executescript(schema)
    # schema is `create table if not exists` — clear rows so reruns start clean
    for table in ("events", "selections", "users"):
        conn.execute("delete from %s" % table)
    conn.commit()
    conn.close()
    identity._resolved.clear()


class FakeClient:
    """Stands in for Bolt's WebClient: users_info from a fixed directory."""

    def __init__(self, directory):
        self.directory = directory
        self.calls = 0

    def users_info(self, user):
        self.calls += 1
        if user not in self.directory:
            raise RuntimeError("user_not_found")
        return {"user": {"profile": {"display_name": self.directory[user]},
                         "name": user.lower()}}


def _name(slack_id):
    row = store._q("select name from users where slack_id = ?", (slack_id,),
                   fetch="one")
    return row["name"] if row else None


def main():
    client = FakeClient({"U1": "Ada Lovelace", "U2": "Ben Okri"})

    # 1) The bug: an event without a users row leaves only the raw ID visible.
    _fresh_db()
    store._q("insert into events (kind, user_slack_id, value) "
             "values ('claimed', 'U1', 3.50)")
    row = store._q(
        "select coalesce(u.name, e.user_slack_id) as display from events e "
        "left join users u on u.slack_id = e.user_slack_id", fetch="one")
    assert row["display"] == "U1", row  # dashboard shows the raw ID

    # 2) ensure_user_name resolves and stores the real name…
    identity.ensure_user_name(client, "U1")
    assert _name("U1") == "Ada Lovelace", _name("U1")
    # …and is cached: a second tap doesn't hit the API again.
    identity.ensure_user_name(client, "U1")
    assert client.calls == 1, client.calls

    # 3) Lookup failure falls back without clobbering or crashing.
    identity.ensure_user_name(client, "U9", fallback="mystery.guest")
    assert _name("U9") == "mystery.guest", _name("U9")
    identity._resolved.clear()
    identity.ensure_user_name(client, "U1")  # lookup ok, name refreshed
    store.ensure_user("U1", None)            # a null name never overwrites
    assert _name("U1") == "Ada Lovelace", _name("U1")

    # 4) Backfill heals historical events/selections with no users row.
    _fresh_db()
    store._q("insert into events (kind, user_slack_id, value) "
             "values ('claimed', 'U1', 3.50)")
    store._q("insert into users (slack_id, name) values ('U2', null)")
    store._q("insert into selections (week, half, user_slack_id) "
             "values ('2026-07-20', 'early', 'U2')")
    assert sorted(store.slack_ids_missing_names()) == ["U1", "U2"]
    identity.backfill_missing_names(client)
    assert _name("U1") == "Ada Lovelace" and _name("U2") == "Ben Okri"
    assert store.slack_ids_missing_names() == []

    print("test_identity: all assertions passed ✅")


if __name__ == "__main__":
    main()
