"""
Covers grocery._absorb / _client — the cookie write-back that keeps the
Sainsbury's session alive across writes instead of dying on the first token
rotation. Uses a throwaway session file; no network.

Run:  .venv/bin/python -m pytest tests/test_grocery_session.py -q
"""
import json
import os
import sys
from datetime import datetime, timezone

from requests.cookies import RequestsCookieJar

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import grocery  # noqa: E402


class _Resp:
    def __init__(self, jar):
        self.cookies = jar


def _jar(**pairs):
    jar = RequestsCookieJar()
    for name, value in pairs.items():
        jar.set(name, value)
    return jar


def _write_session(path, cookies, expires="2020-01-01T00:00:00.000Z"):
    path.write_text(json.dumps({"cookies": cookies, "expiresAt": expires}))


def test_absorb_updates_rotated_token_and_adds_new(tmp_path, monkeypatch):
    session = tmp_path / "session.json"
    _write_session(session, [
        {"name": "WC_AUTHENTICATION_1996215", "value": "OLD"},
        {"name": "JSESSIONID", "value": "j1"},
    ])
    monkeypatch.setattr(grocery, "SESSION_FILE", session)

    # server rotates the auth token and hands back a fresh Akamai cookie
    grocery._absorb(_Resp(_jar(WC_AUTHENTICATION_1996215="NEW", AWSALB="alb1")))

    data = json.loads(session.read_text())
    by_name = {c["name"]: c["value"] for c in data["cookies"]}
    assert by_name["WC_AUTHENTICATION_1996215"] == "NEW"   # rotated value captured
    assert by_name["AWSALB"] == "alb1"                     # brand-new cookie added
    assert by_name["JSESSIONID"] == "j1"                   # untouched cookie preserved
    # local guard pushed into the future so it stops falsely rejecting
    assert datetime.fromisoformat(data["expiresAt"].replace("Z", "+00:00")) > datetime.now(timezone.utc)


def test_client_uses_rotated_token(tmp_path, monkeypatch):
    session = tmp_path / "session.json"
    _write_session(session, [{"name": "WC_AUTHENTICATION_1996215", "value": "OLD"}],
                   expires="2099-01-01T00:00:00.000Z")
    monkeypatch.setattr(grocery, "SESSION_FILE", session)
    monkeypatch.delenv("GROCERY_ANON", raising=False)

    grocery._absorb(_Resp(_jar(WC_AUTHENTICATION_1996215="NEW")))

    s = grocery._client()
    assert "WC_AUTHENTICATION_1996215=NEW" in s.headers["Cookie"]
    assert s.headers["wcauthtoken"] == "NEW"   # header tracks the live cookie, not login


def test_absorb_noop_without_cookies(tmp_path, monkeypatch):
    session = tmp_path / "session.json"
    _write_session(session, [{"name": "JSESSIONID", "value": "j1"}], expires="2099-01-01T00:00:00.000Z")
    monkeypatch.setattr(grocery, "SESSION_FILE", session)
    before = session.read_text()
    grocery._absorb(_Resp(RequestsCookieJar()))   # empty jar → no rewrite
    assert session.read_text() == before
