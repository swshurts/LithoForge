"""Iter-112 tests:
  • POST /api/email/notify (idempotent, validation)
  • GET  /api/admin/marketplace/listings (admin gated)
  • POST /api/admin/marketplace/{job_id}/unlist
  • POST /api/admin/marketplace/bulk-unlist (job_ids & all+confirm)
"""
from __future__ import annotations

import asyncio
import os
import secrets
from datetime import datetime, timezone

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

from tests.conftest import API, BASE_URL  # type: ignore


MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ---------- helpers ---------------------------------------------------------

def _db():
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


def _seed_listing(title: str, price: float = 4.99, user_id: str = "test-user-pytest") -> str:
    job_id = "test-listing-" + secrets.token_urlsafe(6)

    async def _do():
        db = _db()
        await db.jobs.insert_one({
            "job_id": job_id,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc),
            "listing": {
                "visibility": "listed",
                "title": title,
                "description": "iter112 test listing",
                "price_usd": price,
                "license": "All Rights Reserved",
                "listed_at": datetime.now(timezone.utc),
            },
        })
    asyncio.run(_do())
    return job_id


def _cleanup_jobs(job_ids):
    async def _do():
        db = _db()
        await db.jobs.delete_many({"job_id": {"$in": list(job_ids)}})
    asyncio.run(_do())


def _cleanup_email(email: str):
    async def _do():
        db = _db()
        await db.email_signups.delete_many({"email": email})
    asyncio.run(_do())


def _count_email(email: str, source: str) -> int:
    async def _do():
        db = _db()
        return await db.email_signups.count_documents({"email": email, "source": source})
    return asyncio.run(_do())


# ---------- email/notify ---------------------------------------------------

class TestEmailNotify:
    def test_valid_signup_returns_ok(self):
        email = f"test_iter112_{secrets.token_hex(4)}@example.com"
        try:
            r = requests.post(f"{API}/email/notify",
                              json={"email": email, "source": "launch"})
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["ok"] is True
            assert data["email"] == email.lower()
            assert data["source"] == "launch"
            assert _count_email(email.lower(), "launch") == 1
        finally:
            _cleanup_email(email.lower())

    def test_idempotent_on_email_source(self):
        email = f"test_iter112_idem_{secrets.token_hex(4)}@example.com"
        try:
            for _ in range(3):
                r = requests.post(f"{API}/email/notify",
                                  json={"email": email, "source": "launch"})
                assert r.status_code == 200
            assert _count_email(email.lower(), "launch") == 1
        finally:
            _cleanup_email(email.lower())

    def test_different_source_creates_new_doc(self):
        email = f"test_iter112_diff_{secrets.token_hex(4)}@example.com"
        try:
            for src in ["launch", "pricing-pro"]:
                r = requests.post(f"{API}/email/notify",
                                  json={"email": email, "source": src})
                assert r.status_code == 200
            assert _count_email(email.lower(), "launch") == 1
            assert _count_email(email.lower(), "pricing-pro") == 1
        finally:
            _cleanup_email(email.lower())

    def test_invalid_empty_email_returns_400(self):
        r = requests.post(f"{API}/email/notify", json={"email": "", "source": "launch"})
        assert r.status_code == 400
        assert r.json().get("detail") == "Invalid email"

    def test_invalid_missing_at_returns_400(self):
        r = requests.post(f"{API}/email/notify", json={"email": "notanemail.com", "source": "launch"})
        assert r.status_code == 400
        assert r.json().get("detail") == "Invalid email"

    def test_invalid_missing_tld_returns_400(self):
        r = requests.post(f"{API}/email/notify", json={"email": "user@nodot", "source": "launch"})
        assert r.status_code == 400
        assert r.json().get("detail") == "Invalid email"


# ---------- admin marketplace listings -------------------------------------

class TestAdminMarketplaceAuth:
    def test_listings_anon_returns_401(self):
        r = requests.get(f"{API}/admin/marketplace/listings")
        assert r.status_code in (401, 403)

    def test_listings_non_admin_returns_403(self):
        # Build a non-admin user + session
        user_id = "test-nonadmin-" + secrets.token_urlsafe(4)
        token = "tok-" + secrets.token_urlsafe(8)

        async def _seed():
            db = _db()
            now = datetime.now(timezone.utc)
            await db.users.insert_one({
                "user_id": user_id, "email": f"{user_id}@example.com",
                "name": "Non Admin", "tier": "free", "is_admin": False,
                "is_super_admin": False, "is_suspended": False,
                "created_at": now,
            })
            await db.user_sessions.insert_one({
                "user_id": user_id, "session_token": token,
                "expires_at": now.replace(year=now.year + 1),
                "created_at": now,
            })

        async def _clean():
            db = _db()
            await db.users.delete_many({"user_id": user_id})
            await db.user_sessions.delete_many({"user_id": user_id})

        asyncio.run(_seed())
        try:
            r = requests.get(
                f"{API}/admin/marketplace/listings",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 403, r.text
        finally:
            asyncio.run(_clean())


class TestAdminMarketplaceListings:
    def test_listings_admin_returns_seeded_job(self, authed_client):
        job_id = _seed_listing("TEST_iter112 listing")
        try:
            r = authed_client.get(f"{API}/admin/marketplace/listings")
            assert r.status_code == 200, r.text
            data = r.json()
            assert isinstance(data, list)
            row = next((d for d in data if d["job_id"] == job_id), None)
            assert row is not None, "seeded listing not present"
            for key in ("job_id", "user_id", "creator_email", "creator_name",
                        "creator_is_admin", "title", "price_usd", "listed_at"):
                assert key in row, f"missing {key}"
            assert row["title"] == "TEST_iter112 listing"
            assert row["price_usd"] == 4.99
            assert row["creator_is_admin"] is True  # seeded under pytest super-admin user
        finally:
            _cleanup_jobs([job_id])


class TestAdminMarketplaceUnlist:
    def test_unlist_single_removes_listing(self, authed_client):
        job_id = _seed_listing("TEST_iter112 single unlist")
        try:
            r = authed_client.post(f"{API}/admin/marketplace/{job_id}/unlist")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["ok"] is True
            assert body["job_id"] == job_id
            # Verify removal via listings GET
            r2 = authed_client.get(f"{API}/admin/marketplace/listings")
            assert all(d["job_id"] != job_id for d in r2.json())
        finally:
            _cleanup_jobs([job_id])

    def test_unlist_unknown_returns_404(self, authed_client):
        r = authed_client.post(f"{API}/admin/marketplace/no-such-job-xyz/unlist")
        assert r.status_code == 404

    def test_unlist_twice_returns_404(self, authed_client):
        job_id = _seed_listing("TEST_iter112 unlist twice")
        try:
            r1 = authed_client.post(f"{API}/admin/marketplace/{job_id}/unlist")
            assert r1.status_code == 200
            r2 = authed_client.post(f"{API}/admin/marketplace/{job_id}/unlist")
            assert r2.status_code == 404
        finally:
            _cleanup_jobs([job_id])


class TestAdminMarketplaceBulkUnlist:
    def test_bulk_unlist_by_job_ids(self, authed_client):
        ids = [_seed_listing(f"TEST_iter112 bulk {i}") for i in range(2)]
        try:
            r = authed_client.post(f"{API}/admin/marketplace/bulk-unlist",
                                   json={"job_ids": ids})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["ok"] is True
            assert body["unlisted"] == 2
            assert body["requested"] == 2
            # Verify
            r2 = authed_client.get(f"{API}/admin/marketplace/listings")
            remaining = {d["job_id"] for d in r2.json()}
            for jid in ids:
                assert jid not in remaining
        finally:
            _cleanup_jobs(ids)

    def test_bulk_unlist_all_missing_confirm_returns_400(self, authed_client):
        r = authed_client.post(f"{API}/admin/marketplace/bulk-unlist",
                               json={"all": True})
        assert r.status_code == 400

    def test_bulk_unlist_all_wrong_confirm_returns_400(self, authed_client):
        r = authed_client.post(f"{API}/admin/marketplace/bulk-unlist",
                               json={"all": True, "confirm": "unlist all"})
        assert r.status_code == 400

    def test_bulk_unlist_all_succeeds(self, authed_client):
        ids = [_seed_listing(f"TEST_iter112 wipe {i}") for i in range(2)]
        try:
            r = authed_client.post(f"{API}/admin/marketplace/bulk-unlist",
                                   json={"all": True, "confirm": "UNLIST ALL"})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["ok"] is True
            assert body["unlisted"] >= 2
            # All listings should be gone
            r2 = authed_client.get(f"{API}/admin/marketplace/listings")
            assert r2.json() == [] or all(d["job_id"] not in ids for d in r2.json())
        finally:
            _cleanup_jobs(ids)

    def test_bulk_unlist_neither_returns_400(self, authed_client):
        r = authed_client.post(f"{API}/admin/marketplace/bulk-unlist", json={})
        assert r.status_code == 400
