"""
Iter-110 verification tests.

Covers:
 (A) Filament Swap Simulator backend support:
     - /api/filament-library/search?hex=... now returns price_per_kg_usd
     - brand-tier price ordering (Prusament > Bambu > Generic)
     - material ordering (PETG > PLA at the same brand tier)
     - cost estimator honours explicit price_per_kg_usd
 (B) Refactor verification:
     - Stripe checkout routes removed (POST /api/marketplace/{job}/checkout → 404)
     - Braintree marketplace still works (GET /api/braintree/client-token)
     - Buyer download path still works (invalid token → 401 auth_required)
"""
import os
import requests
import pytest

def _load_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k, v)

_load_frontend_env()
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"


# -- A. Filament library: price_per_kg_usd present --------------------------

class TestFilamentLibrarySearchPrice:
    def test_search_returns_price_per_kg_usd(self):
        r = requests.get(f"{API}/filament-library/search",
                         params={"hex": "ff0000", "limit": 4})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "results" in data and len(data["results"]) > 0
        for entry in data["results"]:
            assert "price_per_kg_usd" in entry, f"missing in {entry}"
            assert isinstance(entry["price_per_kg_usd"], (int, float))
            assert entry["price_per_kg_usd"] > 0

    def test_brand_tier_ordering(self):
        """Prusament (premium 1.45×) > Bambu (1.0×) > Generic (0.85×) for same material."""
        r = requests.get(f"{API}/filament-library/search",
                         params={"hex": "ff0000", "limit": 50, "material": "PLA"})
        assert r.status_code == 200, r.text
        results = r.json()["results"]
        # Build {brand_lower: price}
        by_brand = {}
        for e in results:
            by_brand.setdefault(e["brand"].lower(), []).append(e["price_per_kg_usd"])

        def mean(xs):
            return sum(xs) / len(xs)

        prusament = next((mean(v) for k, v in by_brand.items() if "prusa" in k), None)
        bambu     = next((mean(v) for k, v in by_brand.items() if "bambu" in k), None)
        # budget brand: try generic/esun
        budget = None
        for k, v in by_brand.items():
            if "generic" in k or "esun" in k or "atomic" in k:
                budget = mean(v) if budget is None else min(budget, mean(v))
        assert prusament is not None, f"Prusament not found in {list(by_brand.keys())}"
        assert bambu is not None, f"Bambu Lab not found in {list(by_brand.keys())}"
        assert prusament > bambu, f"Prusament {prusament} should be > Bambu {bambu}"
        if budget is not None:
            assert bambu >= budget, f"Bambu {bambu} should be >= budget {budget}"

    def test_petg_more_expensive_than_pla_same_brand(self):
        """At the same brand tier, PETG should be priced > PLA."""
        # Search broad enough to get multiple materials
        r_pla = requests.get(f"{API}/filament-library/search",
                             params={"hex": "000000", "limit": 50, "material": "PLA"})
        r_petg = requests.get(f"{API}/filament-library/search",
                              params={"hex": "000000", "limit": 50, "material": "PETG"})
        assert r_pla.status_code == 200 and r_petg.status_code == 200
        pla = r_pla.json()["results"]
        petg = r_petg.json()["results"]
        # Pick Bambu Lab (standard tier) to compare
        bambu_pla = [e["price_per_kg_usd"] for e in pla if "bambu" in e["brand"].lower()]
        bambu_petg = [e["price_per_kg_usd"] for e in petg if "bambu" in e["brand"].lower()]
        if not bambu_pla or not bambu_petg:
            pytest.skip("Bambu PLA/PETG not both indexed in library")
        avg_pla = sum(bambu_pla) / len(bambu_pla)
        avg_petg = sum(bambu_petg) / len(bambu_petg)
        assert avg_petg > avg_pla, f"PETG {avg_petg} should > PLA {avg_pla}"


# -- A.cont Cost estimator respects explicit price_per_kg_usd ---------------

class TestCostEstimatorExplicitPrice:
    """Unit-level: estimator should pass through explicit per-filament prices."""

    def test_explicit_price_scales_total_cost(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from cost_estimator import estimate_print_costs
        import numpy as np

        # 2-slot layer map, simple geometry
        from types import SimpleNamespace
        layer_map = np.array([[0, 1, 2, 1], [1, 2, 1, 0], [2, 1, 0, 1]], dtype=np.int32)
        filaments_cheap = [
            SimpleNamespace(name="cheap-A", hex="#ffffff", price_per_kg_usd=10.0),
            SimpleNamespace(name="cheap-B", hex="#000000", price_per_kg_usd=10.0),
        ]
        filaments_pricey = [
            SimpleNamespace(name="pricey-A", hex="#ffffff", price_per_kg_usd=80.0),
            SimpleNamespace(name="pricey-B", hex="#000000", price_per_kg_usd=80.0),
        ]
        kwargs = dict(
            layer_map=layer_map,
            layer_height_mm=0.1,
            swap_layer_indices=[1],
            usable_width_mm=40.0,
            usable_height_mm=30.0,
            base_min_layers=2,
            shape="flat",
        )
        cheap = estimate_print_costs(filaments=filaments_cheap, **kwargs)
        pricey = estimate_print_costs(filaments=filaments_pricey, **kwargs)
        cheap_total = cheap.total_cost_usd if hasattr(cheap, "total_cost_usd") else cheap["total_cost_usd"]
        pricey_total = pricey.total_cost_usd if hasattr(pricey, "total_cost_usd") else pricey["total_cost_usd"]
        assert cheap_total > 0
        ratio = pricey_total / cheap_total
        assert 7.0 < ratio < 9.0, f"Expected ~8× ratio, got {ratio:.2f}"


# -- B. Refactor: Stripe routes gone, Braintree still works -----------------

class TestStripeRoutesRemoved:
    def test_marketplace_checkout_route_is_404(self):
        # The legacy POST /api/marketplace/{job}/checkout should no longer exist.
        r = requests.post(f"{API}/marketplace/some-dummy-job/checkout", json={})
        # Acceptable: 404 (route gone) or 405 (method not allowed if a sibling GET still exists).
        # We assert it is NOT a successful checkout / not a 401-auth-required Stripe response.
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:200]}"


class TestBraintreeStillWorks:
    def test_braintree_client_token(self):
        # Actual route is POST /api/marketplace/client-token (from marketplace_braintree.py)
        r = requests.post(f"{API}/marketplace/client-token")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "client_token" in data, f"Response: {data}"
        assert isinstance(data["client_token"], str) and len(data["client_token"]) > 0


class TestBuyerDownloadInvalidToken:
    def test_no_token_no_auth_returns_401(self):
        # Creator flow with no auth → 401 auth_required.
        r = requests.get(f"{API}/export/some-job-id/stl")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"
        body = r.text.lower()
        assert "auth_required" in body or "auth" in body, f"Body: {body[:300]}"

    def test_invalid_token_does_not_crash(self):
        # Buyer flow with bogus token + non-existent job → graceful 4xx (404 or 401), not 500.
        r = requests.get(f"{API}/export/non-existent-job/stl",
                         params={"token": "definitely-not-a-real-token"})
        assert r.status_code in (401, 404), f"Got unexpected status {r.status_code}: {r.text[:200]}"
        # Most importantly: must not be 500 (proves resolve_download_token import works).
        assert r.status_code != 500
