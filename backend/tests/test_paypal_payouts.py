"""PayPal payouts module tests — exercise the mock-mode batch dispatch
end-to-end (no live HTTP calls) and the public API endpoints.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from datetime import datetime, timezone

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

from tests.conftest import API


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db():
    return AsyncIOMotorClient(
        os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    )[os.environ.get("DB_NAME", "test_database")]


def _run(coro):
    return asyncio.run(coro)


def _seed_creator(user_id, email, balance, paypal_email=""):
    async def _do():
        db = _db()
        await db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "email": email,
                    "name": email.split("@")[0],
                    "tier": "pro",
                    "pending_balance_usd": balance,
                    "paypal_email": paypal_email,
                    "is_suspended": False,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    _run(_do())


def _cleanup():
    async def _do():
        db = _db()
        await db.users.delete_many({"user_id": {"$regex": "^payout-test-"}})
        await db.payout_batches.delete_many({})
        await db.payment_transactions.delete_many({"creator_id": {"$regex": "^payout-test-"}})
        # Clear paypal_email + balance fields on the shared pytest user
        # so it never accidentally qualifies as an eligible creator.
        await db.users.update_one(
            {"user_id": "test-user-pytest"},
            {"$unset": {"paypal_email": "", "pending_balance_usd": "", "lifetime_paid_usd": ""}},
        )
    _run(_do())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPayPalPayouts:
    def setup_method(self):
        _cleanup()
        # Ensure mock mode for tests
        os.environ["PAYPAL_CLIENT_ID"] = ""

    def teardown_method(self):
        _cleanup()

    def test_status_default_anonymous(self):
        r = requests.get(f"{API}/payouts/status")
        assert r.status_code == 401

    def test_status_default(self, authed_client):
        r = authed_client.get(f"{API}/payouts/status")
        assert r.status_code == 200
        body = r.json()
        assert body["paypal_email"] == ""
        assert body["payout_threshold_usd"] == 1.0
        assert body["mode"] == "mock"

    def test_set_invalid_email(self, authed_client):
        r = authed_client.post(
            f"{API}/payouts/email",
            json={"paypal_email": "not-an-email"},
        )
        assert r.status_code == 422  # pydantic EmailStr validation

    def test_set_valid_email(self, authed_client):
        r = authed_client.post(
            f"{API}/payouts/email",
            json={"paypal_email": "Creator@Test.com"},
        )
        assert r.status_code == 200
        assert r.json()["paypal_email"] == "creator@test.com"

    def test_settle_credits_pending_balance(self):
        from paypal_payouts import settle_creator_payout

        async def _do():
            db = _db()
            await db.users.update_one(
                {"user_id": "payout-test-creator-1"},
                {"$set": {"user_id": "payout-test-creator-1",
                          "pending_balance_usd": 0.0}},
                upsert=True,
            )
            result = await settle_creator_payout(db, {
                "creator_id": "payout-test-creator-1",
                "creator_payout_usd": 4.99,
                "session_id": "fake-txn",
                "job_id": "fake-job",
            })
            assert result["payout_status"] == "pending"
            user = await db.users.find_one({"user_id": "payout-test-creator-1"})
            assert abs(user["pending_balance_usd"] - 4.99) < 0.01
        _run(_do())

    def test_run_batch_no_eligible_creators(self):
        from paypal_payouts import run_payout_batch

        async def _do():
            db = _db()
            result = await run_payout_batch(db, triggered_by="test")
            assert result["ok"] is True
            assert result["creators"] == 0
            assert result["batch_id"] is None
        _run(_do())

    def test_run_batch_filters_by_threshold(self):
        """Creators below $1 threshold not paid out."""
        from paypal_payouts import run_payout_batch
        _seed_creator("payout-test-below", "below@t.co", 0.50, "below@paypal.com")
        async def _do():
            db = _db()
            result = await run_payout_batch(db, triggered_by="test")
            assert result["creators"] == 0
        _run(_do())

    def test_run_batch_filters_missing_paypal_email(self):
        """Creator with balance but no PayPal email is skipped."""
        from paypal_payouts import run_payout_batch
        _seed_creator("payout-test-noemail", "n@t.co", 5.0, "")
        async def _do():
            db = _db()
            result = await run_payout_batch(db, triggered_by="test")
            assert result["creators"] == 0
        _run(_do())

    def test_run_batch_mock_mode_pays_out(self):
        """End-to-end happy path in mock mode."""
        from paypal_payouts import run_payout_batch
        _seed_creator("payout-test-c1", "c1@t.co", 12.50, "c1@paypal.com")
        _seed_creator("payout-test-c2", "c2@t.co", 3.25, "c2@paypal.com")
        async def _do():
            db = _db()
            # Seed a pending payment_transaction for c1
            await db.payment_transactions.insert_one({
                "creator_id": "payout-test-c1",
                "payout_status": "pending",
                "creator_payout_usd": 12.50,
                "payment_status": "paid",
                "transaction_id": "txn-c1",
                "session_id": "txn-c1",
                "job_id": "job-c1",
                "buyer_email": "buyer@t.co",
                "paid_at": datetime.now(timezone.utc),
            })
            result = await run_payout_batch(db, triggered_by="test")
            assert result["ok"] is True
            assert result["creators"] == 2
            assert abs(result["total_usd"] - 15.75) < 0.01
            assert result["mode"] == "mock"
            assert result["payout_batch_id"].startswith("MOCK-")

            # Pending balances zeroed
            c1 = await db.users.find_one({"user_id": "payout-test-c1"})
            assert abs(c1["pending_balance_usd"]) < 0.01
            # Lifetime updated
            assert abs(c1["lifetime_paid_usd"] - 12.50) < 0.01

            # Batch row exists
            batch = await db.payout_batches.find_one({"batch_id": result["batch_id"]})
            assert batch is not None
            assert batch["status"] == "SUCCESS"
            assert len(batch["items"]) == 2

            # Payment transaction flipped to paid (mock mode)
            txn = await db.payment_transactions.find_one({"creator_id": "payout-test-c1"})
            assert txn["payout_status"] == "paid"
            assert txn["payout_batch_id"] == result["batch_id"]
        _run(_do())

    def test_admin_pending_endpoint(self, authed_client):
        _seed_creator("payout-test-pe", "pe@t.co", 7.25, "pe@paypal.com")
        r = authed_client.get(f"{API}/admin/payouts/pending")
        assert r.status_code == 200
        body = r.json()
        assert body["threshold_usd"] == 1.0
        assert body["eligible_count"] >= 1
        assert body["total_pending_usd"] >= 7.25

    def test_admin_run_endpoint(self, authed_client):
        _seed_creator("payout-test-run", "run@t.co", 2.50, "run@paypal.com")
        r = authed_client.post(f"{API}/admin/payouts/run")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["creators"] >= 1

    def test_admin_batches_list(self, authed_client):
        _seed_creator("payout-test-list", "list@t.co", 5.00, "list@paypal.com")
        authed_client.post(f"{API}/admin/payouts/run")
        r = authed_client.get(f"{API}/admin/payouts/batches")
        assert r.status_code == 200
        body = r.json()
        assert "batches" in body
        assert any(b for b in body["batches"] if b["total_usd"] >= 5.0)

    def test_non_admin_blocked_from_admin_endpoints(self):
        """Anonymous request to /admin/payouts/run gets 401."""
        r = requests.post(f"{API}/admin/payouts/run")
        assert r.status_code == 401

    def test_webhook_item_success_updates_status(self):
        from paypal_payouts import run_payout_batch

        async def _setup_and_test():
            db = _db()
            await db.users.update_one(
                {"user_id": "payout-test-wh"},
                {"$set": {
                    "user_id": "payout-test-wh",
                    "email": "wh@t.co",
                    "pending_balance_usd": 4.00,
                    "paypal_email": "wh@paypal.com",
                    "is_suspended": False,
                }},
                upsert=True,
            )
            await db.payment_transactions.insert_one({
                "creator_id": "payout-test-wh",
                "payout_status": "pending",
                "creator_payout_usd": 4.00,
                "payment_status": "paid",
                "transaction_id": "txn-wh",
                "session_id": "txn-wh",
                "job_id": "job-wh",
                "buyer_email": "buyer@t.co",
                "paid_at": datetime.now(timezone.utc),
            })
            await run_payout_batch(db, triggered_by="test")
            batch = await db.payout_batches.find_one({"items.user_id": "payout-test-wh"})
            assert batch is not None
            sender_item_id = batch["items"][0]["sender_item_id"]
            return sender_item_id

        sid = _run(_setup_and_test())

        # Send a FAILED webhook → balance should be refunded.
        event = {
            "event_type": "PAYMENT.PAYOUTS-ITEM.FAILED",
            "resource": {
                "payout_item": {"sender_item_id": sid},
                "transaction_status": "FAILED",
                "payout_item_id": "pi-wh-1",
            },
        }
        r = requests.post(f"{API}/webhook/paypal-payouts", json=event)
        assert r.status_code == 200

        async def _verify():
            db = _db()
            user = await db.users.find_one({"user_id": "payout-test-wh"})
            # Balance refunded
            assert user["pending_balance_usd"] >= 3.99
            txn = await db.payment_transactions.find_one({"creator_id": "payout-test-wh"})
            assert txn["payout_status"] == "failed"

        _run(_verify())
