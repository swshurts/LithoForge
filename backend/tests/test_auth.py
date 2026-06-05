"""Tests for the Emergent-managed Google Auth integration.

Specifically covers the "clear stale cookie on /auth/me 401" hardening:
when the browser sends a session_token that no longer resolves to an
active session, the server should respond with a Set-Cookie header that
expires the cookie so the browser stops re-sending the dead token.
"""

from __future__ import annotations

import requests

from tests.conftest import API


def test_me_with_valid_token_returns_200(authed_client):
    r = authed_client.get(f"{API}/auth/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "pytest@example.com"
    # A valid /me must NOT clear the cookie — only invalid tokens do.
    set_cookie = r.headers.get("set-cookie", "")
    assert "session_token=;" not in set_cookie.lower()
    assert "session_token=" not in set_cookie.lower() or "Max-Age=0" not in set_cookie


def test_me_without_token_returns_401_no_set_cookie():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code == 401
    # No token was sent, so there's nothing to clear — no Set-Cookie.
    assert "session_token" not in r.headers.get("set-cookie", "").lower()


def test_me_with_stale_bearer_token_clears_cookie():
    """The hardening: if the browser sends a token that doesn't resolve
    to an active session, server responds 401 AND emits a Set-Cookie
    header that expires the cookie so the browser drops it."""
    r = requests.get(
        f"{API}/auth/me",
        headers={"Authorization": "Bearer not-a-real-session-token"},
    )
    assert r.status_code == 401
    set_cookie = r.headers.get("set-cookie", "")
    # Cookie name must appear in the Set-Cookie header with an
    # expiration marker — either an empty value, Max-Age=0, or an
    # Expires in the past. FastAPI's delete_cookie uses Max-Age=0.
    assert "session_token" in set_cookie.lower(), (
        f"Expected Set-Cookie clearing session_token, got: {set_cookie!r}"
    )
    assert (
        "max-age=0" in set_cookie.lower()
        or 'session_token=""' in set_cookie
        or "session_token=;" in set_cookie
    ), f"Set-Cookie not expiring the token: {set_cookie!r}"


def test_me_with_stale_cookie_clears_cookie():
    """Same as above but the dead token is sent via Cookie, not Bearer
    — that's the actual production path."""
    r = requests.get(
        f"{API}/auth/me",
        cookies={"session_token": "definitely-not-a-real-session"},
    )
    assert r.status_code == 401
    set_cookie = r.headers.get("set-cookie", "")
    assert "session_token" in set_cookie.lower()
    assert (
        "max-age=0" in set_cookie.lower()
        or 'session_token=""' in set_cookie
        or "session_token=;" in set_cookie
    ), f"Set-Cookie not expiring the token: {set_cookie!r}"
