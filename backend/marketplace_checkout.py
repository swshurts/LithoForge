"""Marketplace Phase B — Stripe Checkout for guest digital-good purchases.

Buyers (logged-in OR anonymous) can purchase a listed job. After payment:
  - the order is marked `paid` in the `payment_transactions` collection
  - the buyer can download the STL/3MF directly from the success page
  - a one-shot download token is generated so the link is shareable in email

SECURITY NOTES (from the integration playbook):
  - Amount/currency NEVER come from the frontend; always derived from the
    listing on the backend.
  - success_url / cancel_url are built from the frontend-provided
    `origin` so we don't hard-code anything.
  - We create the `payment_transactions` row BEFORE redirecting to Stripe
    with status="initiated" and update it on poll/webhook.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from emergentintegrations.payments.stripe.checkout import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    CheckoutStatusResponse,
    StripeCheckout,
)
from fastapi import APIRouter, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr, Field

# Match the platform-fee constant in marketplace.py (kept here to avoid
# circular imports; if either ever changes update both).
PLATFORM_FEE_PCT = 6.0


class CheckoutCreateIn(BaseModel):
    job_id: str
    buyer_email: EmailStr
    origin_url: str = Field(min_length=8, max_length=500)


class CheckoutCreateOut(BaseModel):
    url: str
    session_id: str


class CheckoutStatusOut(BaseModel):
    status: str
    payment_status: str
    amount_total: int
    currency: str
    job_id: Optional[str] = None
    download_token: Optional[str] = None


def _stripe_client(host_url: str) -> StripeCheckout:
    api_key = os.environ.get("STRIPE_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "Stripe is not configured")
    webhook_url = f"{host_url.rstrip('/')}/api/webhook/stripe"
    return StripeCheckout(api_key=api_key, webhook_url=webhook_url)


def build_checkout_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(tags=["marketplace-checkout"])

    @router.post("/marketplace/{job_id}/checkout", response_model=CheckoutCreateOut)
    async def create_checkout(job_id: str, body: CheckoutCreateIn, request: Request):
        if body.job_id != job_id:
            raise HTTPException(400, "job_id mismatch")

        # Look up the listing from MongoDB. Price comes from the server,
        # never from the request body.
        job = await db.jobs.find_one(
            {"job_id": job_id, "listing.visibility": "listed"},
            {"_id": 0, "job_id": 1, "user_id": 1, "listing": 1},
        )
        if not job:
            raise HTTPException(404, "Listing not found")

        amount = float(job["listing"]["price_usd"])
        if amount <= 0.0:
            raise HTTPException(400, "Listing has no price set")

        host_url = str(request.base_url)
        stripe = _stripe_client(host_url)

        success_url = (
            f"{body.origin_url.rstrip('/')}/marketplace/{job_id}/success"
            "?session_id={CHECKOUT_SESSION_ID}"
        )
        cancel_url = f"{body.origin_url.rstrip('/')}/marketplace/{job_id}"

        fee = round(amount * PLATFORM_FEE_PCT / 100.0, 2)
        creator_payout = round(amount - fee, 2)

        metadata: Dict[str, str] = {
            "job_id": job_id,
            "creator_id": job["user_id"],
            "buyer_email": body.buyer_email,
            "amount_usd": f"{amount:.2f}",
            "platform_fee_usd": f"{fee:.2f}",
            "creator_payout_usd": f"{creator_payout:.2f}",
        }

        req = CheckoutSessionRequest(
            amount=amount,
            currency="usd",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )
        session: CheckoutSessionResponse = await stripe.create_checkout_session(req)

        # Record the pending transaction BEFORE returning the redirect URL.
        await db.payment_transactions.insert_one(
            {
                "session_id": session.session_id,
                "job_id": job_id,
                "creator_id": job["user_id"],
                "buyer_email": body.buyer_email,
                "amount_usd": amount,
                "platform_fee_usd": fee,
                "creator_payout_usd": creator_payout,
                "currency": "usd",
                "status": "initiated",
                "payment_status": "pending",
                "download_token": None,
                "metadata": metadata,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )

        return CheckoutCreateOut(url=session.url, session_id=session.session_id)

    @router.get(
        "/marketplace/checkout/status/{session_id}",
        response_model=CheckoutStatusOut,
    )
    async def checkout_status(session_id: str, request: Request):
        # We rely on the stored transaction to know which job this is for.
        txn = await db.payment_transactions.find_one(
            {"session_id": session_id}, {"_id": 0}
        )
        if not txn:
            raise HTTPException(404, "Transaction not found")

        host_url = str(request.base_url)
        stripe = _stripe_client(host_url)
        try:
            status: CheckoutStatusResponse = await stripe.get_checkout_status(session_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Stripe lookup failed: {exc}") from exc

        update: Dict[str, Any] = {
            "status": status.status,
            "payment_status": status.payment_status,
            "amount_total_cents": status.amount_total,
            "currency": status.currency,
            "updated_at": datetime.now(timezone.utc),
        }

        # Once-only: mint a download token the first time we see `paid`.
        if status.payment_status == "paid" and not txn.get("download_token"):
            token = secrets.token_urlsafe(24)
            update["download_token"] = token
            update["paid_at"] = datetime.now(timezone.utc)
        else:
            token = txn.get("download_token")

        await db.payment_transactions.update_one(
            {"session_id": session_id}, {"$set": update}
        )

        return CheckoutStatusOut(
            status=status.status,
            payment_status=status.payment_status,
            amount_total=status.amount_total,
            currency=status.currency,
            job_id=txn.get("job_id"),
            download_token=token if status.payment_status == "paid" else None,
        )

    @router.post("/webhook/stripe")
    async def stripe_webhook(request: Request):
        host_url = str(request.base_url)
        stripe = _stripe_client(host_url)
        body = await request.body()
        sig = request.headers.get("Stripe-Signature", "")
        try:
            event = await stripe.handle_webhook(body, sig)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"Webhook verification failed: {exc}") from exc

        # Idempotent update: only mint the download token if we haven't yet.
        if event.session_id and event.payment_status == "paid":
            txn = await db.payment_transactions.find_one(
                {"session_id": event.session_id}, {"_id": 0, "download_token": 1}
            )
            if txn and not txn.get("download_token"):
                await db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {
                        "$set": {
                            "status": "complete",
                            "payment_status": "paid",
                            "download_token": secrets.token_urlsafe(24),
                            "paid_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )
        return {"received": True}

    return router


async def resolve_download_token(
    db: AsyncIOMotorDatabase, job_id: str, token: str
) -> Optional[Dict[str, Any]]:
    """Verify a download token grants access to job_id. Returns the
    transaction document or None."""
    txn = await db.payment_transactions.find_one(
        {
            "job_id": job_id,
            "download_token": token,
            "payment_status": "paid",
        },
        {"_id": 0},
    )
    return txn
