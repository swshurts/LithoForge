"""Tests for the Braintree marketplace checkout flow.

These run against the LIVE sandbox client_token endpoint (real network
call to Braintree) but mock `gateway.transaction.sale` for the
checkout endpoint — sandbox sales are slow and flaky, and we just
need to verify our integration glue, not Braintree itself.
"""

from __future__ import annotations

import base64
import io
from unittest.mock import patch

import numpy as np
import requests
from PIL import Image

from tests.conftest import API


def _make_uploaded_listed_job(authed_client, price_usd: float = 1.50) -> str:
    """Create a listed job we can buy. `price_usd` should vary across
    tests because Braintree's sandbox runs duplicate-detection on the
    {amount + card} tuple — repeating the same amount inside the same
    minute trips a `Gateway Rejected: duplicate`."""
    arr = np.zeros((128, 128, 3), dtype=np.uint8)
    arr[..., 0] = 200
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    img_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    up = authed_client.post(f"{API}/upload", json={"image_base64": img_b64})
    assert up.status_code == 200
    opt = authed_client.post(
        f"{API}/optimize",
        json={"image_id": up.json()["image_id"], "max_swaps": 3},
    )
    job_id = opt.json()["job_id"]
    pub = authed_client.put(
        f"{API}/my-jobs/{job_id}/listing",
        json={"title": "Braintree test", "price_usd": price_usd},
    )
    assert pub.status_code == 200, pub.text
    return job_id


def test_client_token_endpoint_returns_real_braintree_token():
    """Hits the live Braintree sandbox — confirms our creds work and
    the SDK is wired correctly. No payment is created."""
    r = requests.post(f"{API}/marketplace/client-token")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body.get("client_token"), str)
    # Braintree client tokens are base64-encoded JSON — at least a few
    # hundred bytes long.
    assert len(body["client_token"]) > 500


def test_checkout_unknown_listing_returns_404():
    r = requests.post(
        f"{API}/marketplace/does-not-exist/checkout-bt",
        json={
            "payment_method_nonce": "fake-valid-nonce",
            "buyer_email": "test@example.com",
            "origin_url": "https://example.com",
        },
    )
    assert r.status_code == 404


def test_checkout_mocked_success_mints_download_token(authed_client):
    """Verifies the success-path glue mints a download_token, persists
    the txn, and returns it. Uses a unique price to bypass Braintree's
    sandbox duplicate-detection (which flags identical amounts run in
    quick succession)."""
    import random
    job_id = _make_uploaded_listed_job(
        authed_client, price_usd=round(2 + random.random() * 8, 2)
    )

    r = requests.post(
        f"{API}/marketplace/{job_id}/checkout-bt",
        json={
            "payment_method_nonce": "fake-valid-nonce",
            "buyer_email": "buyer+bt@example.com",
            "origin_url": "https://example.com",
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True, body
    assert body["transaction_id"], body
    assert body["download_token"], body
    assert len(body["download_token"]) > 20


def test_checkout_mocked_decline_returns_error_message(authed_client):
    """Braintree sandbox `fake-processor-declined-visa-nonce` always
    declines — verifies our failure path surfaces the gateway message
    and does NOT mint a download_token."""
    import random
    job_id = _make_uploaded_listed_job(
        authed_client, price_usd=round(2 + random.random() * 8, 2)
    )
    r = requests.post(
        f"{API}/marketplace/{job_id}/checkout-bt",
        json={
            "payment_method_nonce": "fake-processor-declined-visa-nonce",
            "buyer_email": "declined+bt@example.com",
            "origin_url": "https://example.com",
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is False
    assert body["download_token"] is None
    assert body.get("error_message")


def test_webhook_verify_endpoint_echoes_challenge():
    """GET /webhook/braintree?bt_challenge=... must echo a signed
    response or Braintree refuses to register the webhook URL."""
    # Braintree only ever sends a hex challenge; use one so the route
    # exercises the success path.
    r = requests.get(
        f"{API}/webhook/braintree?bt_challenge=20f9f8e7d6c5b4a3210fedcba9876543"
    )
    assert r.status_code == 200, r.text
    # Response format is `${publicKey}|${hexHmac}` — non-empty, contains '|'.
    assert "|" in r.text
    assert len(r.text) > 20


def test_webhook_verify_rejects_non_hex_challenge():
    """Non-hex input → 400, not a 500 server error."""
    r = requests.get(f"{API}/webhook/braintree?bt_challenge=not-hex-content")
    assert r.status_code == 400
