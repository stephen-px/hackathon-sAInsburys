"""Resolve Slack user IDs to human names and persist them in the users table.

The dashboard falls back to the raw slack_id (U87XZ...) for anyone without a
name in `users`, so every handler that records a user event calls
ensure_user_name() to keep the table populated.
"""
import store

_resolved = set()  # slack_ids we already stored a real name for, this process


def ensure_user_name(client, user_id, fallback=None):
    """Make sure `users` has a human-readable name for user_id.

    Hits users_info once per user per process; must never raise — a name
    lookup failing can't be allowed to break the claim/check-in that
    triggered it.
    """
    if not user_id or user_id in _resolved:
        return
    name = None
    try:
        info = client.users_info(user=user_id)["user"]
        profile = info.get("profile") or {}
        name = (profile.get("display_name") or profile.get("real_name")
                or info.get("real_name") or info.get("name"))
    except Exception:
        pass
    name = name or fallback
    try:
        store.ensure_user(user_id, name)
    except Exception:
        return
    if name:
        _resolved.add(user_id)


def backfill_missing_names(client):
    """Resolve every slack_id already in events/selections that still has no
    name — heals rows recorded before ensure_user_name() existed."""
    missing = store.slack_ids_missing_names()
    for user_id in missing:
        ensure_user_name(client, user_id)
    if missing:
        print("[identity] backfilled names for %d user(s)" % len(missing), flush=True)
