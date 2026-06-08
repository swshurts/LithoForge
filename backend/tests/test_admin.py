"""Tests for the admin moderation API.

The pytest test user is seeded with is_super_admin=True (see conftest)
so the privileged endpoints are reachable without going through the
real Google OAuth flow.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

import requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import os

from tests.conftest import API


def _seed_other_user(email: str = "other@example.com", **extra) -> str:
    """Insert a non-admin user we can poke at. Returns the user_id."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    user_id = f"u_{secrets.token_hex(6)}"

    async def _do():
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        doc = {
            "user_id": user_id,
            "email": email,
            "name": "Other User",
            "is_admin": False,
            "is_super_admin": False,
            "is_suspended": False,
            "ai_quota_override": None,
            "created_at": datetime.now(timezone.utc),
        }
        doc.update(extra)
        await db.users.insert_one(doc)
        client.close()
    asyncio.run(_do())
    return user_id


def test_admin_me_returns_super_admin_user(authed_client):
    r = authed_client.get(f"{API}/admin/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "pytest@example.com"
    assert body["is_super_admin"] is True


def test_admin_me_403_for_anonymous():
    r = requests.get(f"{API}/admin/me")
    # require_user_dep returns 401 when no token present.
    assert r.status_code in (401, 403)


def test_admin_users_list_paginates_and_searches(authed_client):
    target_id = _seed_other_user(email="needle@findme.test")
    # Full list works.
    r = authed_client.get(f"{API}/admin/users?limit=5")
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    assert len(items) <= 5
    # Search finds the unique email.
    r = authed_client.get(f"{API}/admin/users?q=needle")
    assert r.status_code == 200
    found = [u for u in r.json() if u["user_id"] == target_id]
    assert len(found) == 1
    assert found[0]["email"] == "needle@findme.test"


def test_toggle_admin_writes_audit_entry(authed_client):
    target_id = _seed_other_user(email="promote@test.com")
    # Initial: is_admin false.
    r = authed_client.get(f"{API}/admin/users/{target_id}")
    assert r.json()["is_admin"] is False
    # Promote.
    r = authed_client.post(f"{API}/admin/users/{target_id}/admin")
    assert r.status_code == 200, r.text
    assert r.json()["is_admin"] is True
    # Demote.
    r = authed_client.post(f"{API}/admin/users/{target_id}/admin")
    assert r.json()["is_admin"] is False
    # Audit log has both entries.
    r = authed_client.get(f"{API}/admin/audit?action=toggle_admin&limit=10")
    actions = r.json()
    target_actions = [a for a in actions if a["target_user_id"] == target_id]
    assert len(target_actions) >= 2


def test_toggle_admin_refuses_to_touch_super_admins(authed_client):
    """Super-admins are managed via SUPER_ADMIN_EMAILS; the UI must
    not be able to flip their is_admin flag."""
    target_id = _seed_other_user(
        email="protected@test.com", is_super_admin=True, is_admin=True
    )
    r = authed_client.post(f"{API}/admin/users/{target_id}/admin")
    assert r.status_code == 400


def test_toggle_suspend_kills_sessions(authed_client):
    """Suspending a user must also invalidate any sessions they hold,
    otherwise a stale cookie would keep working."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    target_id = _seed_other_user(email="suspendme@test.com")
    # Give them an active session.
    target_token = "ban-target-" + secrets.token_urlsafe(8)

    async def _seed_session():
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        await db.user_sessions.insert_one({
            "user_id": target_id,
            "session_token": target_token,
            "expires_at": datetime.now(timezone.utc).replace(year=2030),
            "created_at": datetime.now(timezone.utc),
        })
        client.close()
    asyncio.run(_seed_session())

    # Confirm /auth/me sees them as valid.
    r = requests.get(f"{API}/auth/me", cookies={"session_token": target_token})
    assert r.status_code == 200

    # Suspend.
    r = authed_client.post(f"{API}/admin/users/{target_id}/suspend")
    assert r.status_code == 200
    assert r.json()["is_suspended"] is True

    # Their session must now 401.
    r = requests.get(f"{API}/auth/me", cookies={"session_token": target_token})
    assert r.status_code == 401


def test_patch_user_updates_ai_quota_override(authed_client):
    target_id = _seed_other_user(email="quota@test.com")
    r = authed_client.patch(
        f"{API}/admin/users/{target_id}", json={"ai_quota_override": 250}
    )
    assert r.status_code == 200
    assert r.json()["ai_quota_override"] == 250
    # Setting to null clears it.
    r = authed_client.patch(
        f"{API}/admin/users/{target_id}", json={"ai_quota_override": None}
    )
    assert r.status_code == 200
    assert r.json()["ai_quota_override"] is None
    # Empty body → 400 (nothing to update).
    r = authed_client.patch(f"{API}/admin/users/{target_id}", json={})
    assert r.status_code == 400


def test_audit_log_filters_by_action(authed_client):
    target_id = _seed_other_user(email="audit-filter@test.com")
    authed_client.post(f"{API}/admin/users/{target_id}/suspend")
    r = authed_client.get(f"{API}/admin/audit?action=toggle_suspend&limit=5")
    assert r.status_code == 200
    for entry in r.json():
        assert entry["action"] == "toggle_suspend"
