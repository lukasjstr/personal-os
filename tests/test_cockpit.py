"""V3 P12 — Cockpit API smoke tests.

The /api/cockpit endpoint is composed from many other modules; we just
verify the route + payload shape against a real user.
"""
import os

import pytest
import requests


API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
API_TOKEN = os.environ.get("API_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}

requires_token = pytest.mark.skipif(not API_TOKEN, reason="API_TOKEN not set")


@requires_token
def test_cockpit_endpoint_returns_required_keys() -> None:
    res = requests.get(f"{API_BASE}/api/cockpit", headers=HEADERS, timeout=10)
    assert res.status_code == 200
    data = res.json()
    for key in (
        "date", "life_score", "life_score_trend", "active_objectives",
        "krs_at_risk", "energy", "areas", "weekly_priorities",
        "festnagel", "streaks_at_risk", "cuts_this_week",
    ):
        assert key in data, f"missing key: {key}"


@requires_token
def test_cockpit_areas_have_expected_shape() -> None:
    res = requests.get(f"{API_BASE}/api/cockpit", headers=HEADERS, timeout=10)
    data = res.json()
    assert isinstance(data["areas"], list)
    if data["areas"]:
        a = data["areas"][0]
        for key in ("id", "name", "short_code", "color",
                    "active_objectives", "stale_days", "score"):
            assert key in a, f"area missing key: {key}"


@requires_token
def test_cockpit_festnagel_never_empty() -> None:
    res = requests.get(f"{API_BASE}/api/cockpit", headers=HEADERS, timeout=10)
    data = res.json()
    assert isinstance(data["festnagel"], str)
    assert len(data["festnagel"]) > 10
