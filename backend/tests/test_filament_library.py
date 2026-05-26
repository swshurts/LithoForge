"""Tests for the manufacturer filament-library endpoints."""
from __future__ import annotations

import requests

from conftest import API


def test_brands_endpoint_returns_all_nine():
    r = requests.get(f"{API}/filament-library/brands")
    assert r.status_code == 200
    brands = r.json()["brands"]
    expected = {
        "Bambu Lab", "Polymaker", "Prusament", "eSun", "Sunlu",
        "Overture", "Hatchbox", "uJoybio3d", "FlashForge",
    }
    assert expected.issubset(set(brands))


def test_browse_default_returns_full_catalog():
    r = requests.get(f"{API}/filament-library")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 80, "catalog should have at least 80 entries"
    sample = body["filaments"][0]
    for k in ("id", "brand", "name", "hex", "td", "finish"):
        assert k in sample


def test_browse_brand_filter():
    r = requests.get(f"{API}/filament-library?brand=Bambu Lab")
    assert r.status_code == 200
    items = r.json()["filaments"]
    assert len(items) > 0
    assert all(f["brand"] == "Bambu Lab" for f in items)


def test_search_orange_finds_orange():
    r = requests.get(f"{API}/filament-library/search?hex=%23FF7A00&limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["target_hex"] == "#FF7A00"
    assert body["algorithm"] == "de76"
    results = body["results"]
    assert len(results) == 5
    # The very best match should be reasonably close — ΔE76 over-counts
    # saturated-orange hue differences vs ΔE2000, so 15 is a safe bound
    # for "in the same family".
    assert results[0]["delta_e"] < 15, results[0]
    # Results sorted ascending.
    for a, b in zip(results, results[1:]):
        assert a["delta_e"] <= b["delta_e"]
    # Top match should be an orange-named SKU.
    assert "orange" in results[0]["name"].lower() or "mandarin" in results[0]["name"].lower()


def test_search_de2000_algorithm():
    r = requests.get(
        f"{API}/filament-library/search?hex=%2300AE42&algo=de2000&limit=3",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["algorithm"] == "de2000"
    assert len(body["results"]) == 3
    # First match should be a green/Bambu green.
    assert body["results"][0]["delta_e"] < 5


def test_search_invalid_hex_returns_400():
    r = requests.get(f"{API}/filament-library/search?hex=notahex")
    assert r.status_code == 400


def test_private_library_requires_auth():
    r = requests.get(f"{API}/filament-library/mine")
    assert r.status_code in (401, 403)


def test_private_library_add_list_delete(authed_client):
    # Add
    payload = {"brand": "TestBrand", "name": "Test Crimson",
               "hex": "#C40D2B", "td": 1.2, "finish": "matte"}
    r = authed_client.post(f"{API}/filament-library/mine", json=payload)
    assert r.status_code == 200, r.text
    fid = r.json()["id"]
    assert fid.startswith("u_")
    # List
    r = authed_client.get(f"{API}/filament-library/mine")
    assert r.status_code == 200
    ids = [f["id"] for f in r.json()["filaments"]]
    assert fid in ids
    # Search with include_private should include the private SKU
    r = authed_client.get(
        f"{API}/filament-library/search?hex=%23C40D2B&include_private=true&limit=20",
    )
    found = [x for x in r.json()["results"] if x.get("id") == fid]
    assert found, "private SKU should be returned when include_private=true"
    assert found[0]["source"] == "private"
    # Delete
    r = authed_client.delete(f"{API}/filament-library/mine/{fid}")
    assert r.status_code == 200
    r = authed_client.delete(f"{API}/filament-library/mine/{fid}")
    assert r.status_code == 404


def test_suggest_endpoint(authed_client):
    payload = {
        "brand": "MysteryFilament", "name": "Forest Mist",
        "hex": "#3B6B58", "td": 1.4, "finish": "matte",
        "submitter_email": "user@example.com",
        "notes": "I bought a sample reel and it prints well.",
    }
    r = authed_client.post(f"{API}/filament-library/suggest", json=payload)
    assert r.status_code == 200
    assert r.json() == {"ok": True}
