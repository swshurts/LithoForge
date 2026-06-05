"""Tests for the Emergent-managed Google Auth integration.

The earlier "auto-clear stale cookie on /auth/me 401" behaviour was
reverted because it raced with React StrictMode's double-effect-invoke
during sign-in — see git history. /auth/me now plainly returns 401
when a session token is missing or stale; stale cookies are
overwritten atomically on the next successful /auth/session.
"""

from __future__ import annotations

import requests

from tests.conftest import API


def test_me_with_valid_token_returns_200(authed_client):
    r = authed_client.get(f"{API}/auth/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "pytest@example.com"


def test_me_without_token_returns_401():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code == 401


def test_me_with_stale_bearer_token_returns_401():
    r = requests.get(
        f"{API}/auth/me",
        headers={"Authorization": "Bearer not-a-real-session-token"},
    )
    assert r.status_code == 401


def test_me_with_stale_cookie_returns_401():
    r = requests.get(
        f"{API}/auth/me",
        cookies={"session_token": "definitely-not-a-real-session"},
    )
    assert r.status_code == 401


def test_me_401_does_not_clear_valid_cookie():
    """Regression: ensure a 401 response does NOT carry a Set-Cookie
    that expires the session_token. We rolled back the auto-clear
    behaviour because it raced with React StrictMode and zapped
    freshly-set sessions, causing an infinite sign-in loop."""
    r = requests.get(
        f"{API}/auth/me",
        cookies={"session_token": "stale"},
    )
    assert r.status_code == 401
    set_cookie = r.headers.get("set-cookie", "")
    # Cloudflare may set its own __cf_bm cookie — that's fine. What we
    # MUST NOT see is a Set-Cookie clearing our session_token.
    assert "session_token=" not in set_cookie.lower(), (
        f"401 must not Set-Cookie session_token (would zap live sessions during sign-in race): {set_cookie!r}"
    )
