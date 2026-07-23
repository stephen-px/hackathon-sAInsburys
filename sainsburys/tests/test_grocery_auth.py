"""
Covers grocery.start_login/submit_mfa — the HTTP client half of /authenticate
(the other half, vendor/uk-grocery-cli's auth-server, is exercised manually
with curl since it drives a real Playwright browser).

Run:  .venv/bin/python tests/test_grocery_auth.py
"""
import os
import sys
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import grocery  # noqa: E402


def _fake_response(payload):
    resp = mock.Mock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def main():
    with mock.patch("grocery.requests.post") as post:
        post.return_value = _fake_response({"status": "mfa_required", "handle": "abc123"})
        result = grocery.start_login("me@example.com", "hunter2")
        assert result == {"status": "mfa_required", "handle": "abc123"}, result
        url, kwargs = post.call_args[0][0], post.call_args[1]
        assert url == grocery.AUTH_SERVER + "/login/start", url
        assert kwargs["json"] == {"email": "me@example.com", "password": "hunter2"}, kwargs

    with mock.patch("grocery.requests.post") as post:
        post.return_value = _fake_response({"status": "ok"})
        result = grocery.submit_mfa("abc123", "654321")
        assert result == {"status": "ok"}, result
        url, kwargs = post.call_args[0][0], post.call_args[1]
        assert url == grocery.AUTH_SERVER + "/login/mfa", url
        assert kwargs["json"] == {"handle": "abc123", "code": "654321"}, kwargs

    with mock.patch("grocery.requests.post") as post:
        post.return_value = _fake_response({"status": "error", "message": "MFA verification failed"})
        result = grocery.submit_mfa("expired", "000000")
        assert result["status"] == "error", result

    print("PASS: grocery.start_login/submit_mfa hit the right auth-server endpoints")


if __name__ == "__main__":
    main()
