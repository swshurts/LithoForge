"""Marketplace Phase C — Stripe Connect (Express) creator payouts.

When a creator wants to receive payouts from marketplace sales, they go
through Stripe's hosted Express onboarding flow. We store their connected
`stripe_account_id` on their user document and, after every sale clears,
issue a separate Transfer for their share of the price (price − 6% fee).

If a creator hasn't onboarded yet, sales still complete but the creator's
share is logged as `payout_pending` on the transaction; we can settle
those manually or after they onboard later.

NOTE: this module talks to Stripe directly via the `stripe` Python SDK
(rather than through emergentintegrations) because Stripe Connect Express
endpoints aren't exposed by the wrapper. Buyer-facing checkout is still
handled by emergentintegrations in marketplace_checkout.py.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger("lithoforge.payouts")


def _stripe_key() -> str:
    key = os.environ.get("STRIPE_API_KEY", "")
    if not key:
        raise HTTPException(500, "Stripe is not configured")
    return key


def _stripe_call(fn, *args, **kwargs):
    """Run a synchronous stripe SDK call and surface a friendly error
    message if it fails."""
    stripe.api_key = _stripe_key()
    try:
        return fn(*args, **kwargs)
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        logger.warning("Stripe error: %s", exc.user_message or str(exc))
        raise HTTPException(502, exc.user_message or str(exc)) from exc


# ---------------------------------------------------------------------------
# Connect account lifecycle
# ---------------------------------------------------------------------------

def create_express_account(email: str, country: str = "US") -> str:
    """Create a new Connect Express account for a creator. Returns the
    account id."""
    acct = _stripe_call(
        stripe.Account.create,
        type="express",
        country=country,
        email=email,
        capabilities={
            "transfers": {"requested": True},
            "card_payments": {"requested": True},
        },
    )
    return acct["id"]


def create_account_link(
    account_id: str, refresh_url: str, return_url: str
) -> str:
    """Build a one-shot URL for the creator to complete Express onboarding."""
    link = _stripe_call(
        stripe.AccountLink.create,
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return link["url"]


def fetch_account_status(account_id: str) -> Dict[str, Any]:
    """Look up whether the connected creator can receive payouts."""
    acct = _stripe_call(stripe.Account.retrieve, account_id)
    return {
        "account_id": acct["id"],
        "charges_enabled": bool(acct.get("charges_enabled")),
        "payouts_enabled": bool(acct.get("payouts_enabled")),
        "details_submitted": bool(acct.get("details_submitted")),
        "email": acct.get("email", ""),
    }


def transfer_to_creator(
    *,
    amount_usd: float,
    destination_account: str,
    transfer_group: str,
    description: str = "",
) -> str:
    """Send the creator's share of a sale to their connected account.
    Returns the transfer id."""
    amount_cents = int(round(amount_usd * 100))
    transfer = _stripe_call(
        stripe.Transfer.create,
        amount=amount_cents,
        currency="usd",
        destination=destination_account,
        transfer_group=transfer_group,
        description=description or "Lithoforge marketplace payout",
    )
    return transfer["id"]


# ---------------------------------------------------------------------------
# Per-user persistence
# ---------------------------------------------------------------------------

async def get_user_connect(
    db: AsyncIOMotorDatabase, user_id: str
) -> Dict[str, Any]:
    """Return the user's Connect state (account_id, payouts_enabled, etc).
    Empty dict if the user hasn't started onboarding."""
    doc = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "stripe_account_id": 1, "payouts_enabled": 1,
         "charges_enabled": 1, "payout_updated_at": 1},
    )
    return doc or {}


async def save_user_connect_state(
    db: AsyncIOMotorDatabase,
    user_id: str,
    *,
    stripe_account_id: Optional[str] = None,
    charges_enabled: Optional[bool] = None,
    payouts_enabled: Optional[bool] = None,
) -> None:
    update: Dict[str, Any] = {"payout_updated_at": datetime.now(timezone.utc)}
    if stripe_account_id is not None:
        update["stripe_account_id"] = stripe_account_id
    if charges_enabled is not None:
        update["charges_enabled"] = charges_enabled
    if payouts_enabled is not None:
        update["payouts_enabled"] = payouts_enabled
    await db.users.update_one({"user_id": user_id}, {"$set": update})


# ---------------------------------------------------------------------------
# FastAPI router
# ---------------------------------------------------------------------------

class OnboardStartIn(BaseModel):
    return_url: str = Field(min_length=8, max_length=500)
    refresh_url: str = Field(min_length=8, max_length=500)


class OnboardStartOut(BaseModel):
    url: str
    account_id: str
    payouts_enabled: bool


class PayoutStatusOut(BaseModel):
    has_account: bool = False
    account_id: str = ""
    charges_enabled: bool = False
    payouts_enabled: bool = False
    details_submitted: bool = False


def build_payouts_router(
    db: AsyncIOMotorDatabase, require_user
) -> APIRouter:
    router = APIRouter(tags=["payouts"])

    @router.post("/payouts/onboard", response_model=OnboardStartOut)
    async def start_onboarding(body: OnboardStartIn, user=Depends(require_user)):
        existing = await get_user_connect(db, user.user_id)
        account_id = existing.get("stripe_account_id") or ""
        if not account_id:
            account_id = create_express_account(email=user.email)
            await save_user_connect_state(
                db, user.user_id,
                stripe_account_id=account_id,
                charges_enabled=False,
                payouts_enabled=False,
            )
        url = create_account_link(account_id, body.refresh_url, body.return_url)
        return OnboardStartOut(
            url=url,
            account_id=account_id,
            payouts_enabled=bool(existing.get("payouts_enabled")),
        )

    @router.get("/payouts/status", response_model=PayoutStatusOut)
    async def status(user=Depends(require_user)):
        record = await get_user_connect(db, user.user_id)
        account_id = record.get("stripe_account_id") or ""
        if not account_id:
            return PayoutStatusOut()
        # Refresh from Stripe so the UI reflects any recent KYC updates.
        try:
            live = fetch_account_status(account_id)
        except HTTPException:
            # If Stripe is down, return whatever we have cached.
            return PayoutStatusOut(
                has_account=True,
                account_id=account_id,
                charges_enabled=bool(record.get("charges_enabled")),
                payouts_enabled=bool(record.get("payouts_enabled")),
            )
        await save_user_connect_state(
            db, user.user_id,
            charges_enabled=live["charges_enabled"],
            payouts_enabled=live["payouts_enabled"],
        )
        return PayoutStatusOut(
            has_account=True,
            account_id=account_id,
            charges_enabled=live["charges_enabled"],
            payouts_enabled=live["payouts_enabled"],
            details_submitted=live["details_submitted"],
        )

    @router.get("/payouts/transactions")
    async def list_transactions(user=Depends(require_user)):
        """Lifetime payouts ledger for a creator — what's been transferred
        + what's still pending (sales where the creator hadn't onboarded
        yet)."""
        cursor = db.payment_transactions.find(
            {"creator_id": user.user_id, "payment_status": "paid"},
            {
                "_id": 0,
                "session_id": 1,
                "job_id": 1,
                "amount_usd": 1,
                "creator_payout_usd": 1,
                "platform_fee_usd": 1,
                "transfer_id": 1,
                "payout_status": 1,
                "buyer_email": 1,
                "paid_at": 1,
                "transfer_failed_reason": 1,
            },
        ).sort("paid_at", -1).limit(200)
        items = await cursor.to_list(200)
        for it in items:
            if isinstance(it.get("paid_at"), datetime):
                it["paid_at"] = it["paid_at"].astimezone(timezone.utc).isoformat()
        total_paid = sum(
            float(it.get("creator_payout_usd", 0))
            for it in items if it.get("payout_status") == "transferred"
        )
        total_pending = sum(
            float(it.get("creator_payout_usd", 0))
            for it in items
            if it.get("payout_status") in (None, "pending", "owed")
        )
        return {
            "transactions": items,
            "total_paid_usd": round(total_paid, 2),
            "total_pending_usd": round(total_pending, 2),
        }

    return router


# ---------------------------------------------------------------------------
# Settlement helper used by the checkout flow
# ---------------------------------------------------------------------------

async def settle_creator_payout(
    db: AsyncIOMotorDatabase,
    txn: Dict[str, Any],
) -> Dict[str, Any]:
    """Called immediately after a transaction's payment_status becomes
    paid. Tries to transfer the creator's share to their connected
    account. Returns a dict {payout_status, transfer_id, reason}.

    Never raises — failures are recorded on the transaction so the
    rest of the success flow (email, downloads) keeps going.
    """
    creator_id = txn.get("creator_id")
    creator_payout = float(txn.get("creator_payout_usd", 0))
    session_id = txn.get("session_id", "")

    if not creator_id or creator_payout <= 0:
        return {"payout_status": "skipped", "transfer_id": None, "reason": "no payout owed"}

    connect = await get_user_connect(db, creator_id)
    account_id = connect.get("stripe_account_id") or ""
    if not account_id or not connect.get("payouts_enabled"):
        # Creator hasn't onboarded — record as owed and continue.
        return {
            "payout_status": "owed",
            "transfer_id": None,
            "reason": "creator has not completed Stripe Connect onboarding",
        }

    try:
        transfer_id = transfer_to_creator(
            amount_usd=creator_payout,
            destination_account=account_id,
            transfer_group=session_id,
            description=f"Lithoforge sale {txn.get('job_id', '')}",
        )
        return {"payout_status": "transferred", "transfer_id": transfer_id, "reason": ""}
    except HTTPException as exc:
        logger.warning("Transfer failed for txn %s: %s", session_id, exc.detail)
        return {
            "payout_status": "failed",
            "transfer_id": None,
            "reason": str(exc.detail)[:300],
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected transfer error: %s", exc)
        return {
            "payout_status": "failed",
            "transfer_id": None,
            "reason": str(exc)[:300],
        }
