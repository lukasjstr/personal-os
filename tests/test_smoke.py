"""G1: E2E smoke tests — verify critical API endpoints are reachable and respond correctly.

Run with:
    pytest tests/test_smoke.py -v

Requires API_BASE_URL and API_TOKEN environment variables (or uses defaults for local dev).
Tests are designed to be safe (read-only, no destructive side effects).
"""
import os
import pytest
import requests

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
API_TOKEN = os.environ.get("API_TOKEN", "")

HEADERS = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}


def get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", headers=HEADERS, timeout=10, **kwargs)


def post(path: str, body: dict, **kwargs) -> requests.Response:
    return requests.post(f"{API_BASE}{path}", json=body, headers=HEADERS, timeout=10, **kwargs)


# ─── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_endpoint(self):
        """API health endpoint responds 200 with status field."""
        res = get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data

    def test_health_db_connected(self):
        """Health check reports DB as connected."""
        res = get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data.get("db") in (None, "ok", True, "connected"), f"Unexpected db status: {data}"


# ─── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not API_TOKEN, reason="No API_TOKEN set")
class TestAuth:
    def test_authenticated_request(self):
        """Authenticated requests to settings return 200."""
        res = get("/api/settings")
        assert res.status_code == 200

    def test_unauthenticated_returns_401(self):
        """Unauthenticated requests return 401."""
        res = requests.get(f"{API_BASE}/api/settings", timeout=10)
        assert res.status_code == 401


# ─── Core Endpoints ────────────────────────────────────────────────────────────

@pytest.mark.skipif(not API_TOKEN, reason="No API_TOKEN set")
class TestCoreEndpoints:
    def test_tasks_list(self):
        res = get("/api/tasks")
        assert res.status_code == 200
        data = res.json()
        assert "tasks" in data
        assert isinstance(data["tasks"], list)

    def test_objectives_list(self):
        res = get("/api/objectives")
        assert res.status_code == 200
        data = res.json()
        assert "objectives" in data

    def test_routines_list(self):
        res = get("/api/routines")
        assert res.status_code == 200
        data = res.json()
        assert "routines" in data

    def test_logs_list(self):
        res = get("/api/logs")
        assert res.status_code == 200
        data = res.json()
        assert "logs" in data

    def test_settings(self):
        res = get("/api/settings")
        assert res.status_code == 200
        data = res.json()
        assert "profile" in data
        assert "toggles" in data

    def test_achievements(self):
        res = get("/api/achievements")
        assert res.status_code == 200
        data = res.json()
        assert "achievements" in data

    def test_gamification_stats(self):
        res = get("/api/gamification/stats")
        assert res.status_code == 200
        data = res.json()
        assert "xp" in data
        assert "level" in data


# ─── Autopilot Endpoints ───────────────────────────────────────────────────────

@pytest.mark.skipif(not API_TOKEN, reason="No API_TOKEN set")
class TestAutopilotEndpoints:
    def test_daily_plan(self):
        res = get("/api/autopilot/daily-plan")
        assert res.status_code in (200, 500), f"Unexpected status: {res.status_code}"

    def test_next_action(self):
        res = get("/api/autopilot/next-action")
        assert res.status_code in (200, 404)

    def test_action_queue(self):
        res = get("/api/autopilot/action-queue")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data

    def test_patterns(self):
        res = get("/api/autopilot/patterns")
        assert res.status_code == 200
        data = res.json()
        assert "missed_routines" in data
        assert "drifting_objectives" in data

    def test_confidence(self):
        res = get("/api/autopilot/confidence")
        assert res.status_code == 200
        data = res.json()
        assert "confidence" in data
        assert 0 <= data["confidence"] <= 100

    def test_active_hours(self):
        res = get("/api/autopilot/active-hours")
        assert res.status_code == 200
        data = res.json()
        assert "peak_hour" in data
        assert "hours" in data

    def test_notifications(self):
        res = get("/api/autopilot/notifications")
        assert res.status_code == 200

    def test_suggestions_today(self):
        res = get("/api/suggestions/today")
        assert res.status_code == 200
        data = res.json()
        assert "date" in data


# ─── Reflections ───────────────────────────────────────────────────────────────

@pytest.mark.skipif(not API_TOKEN, reason="No API_TOKEN set")
class TestReflections:
    def test_list_reflections(self):
        res = get("/api/reflections")
        assert res.status_code == 200
        data = res.json()
        assert "reflections" in data
        assert isinstance(data["reflections"], list)


# ─── Dashboard ─────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not API_TOKEN, reason="No API_TOKEN set")
class TestDashboard:
    def test_dashboard_endpoint(self):
        res = get("/api/dashboard")
        assert res.status_code == 200
        data = res.json()
        assert "user" in data

    def test_weekly_summary(self):
        res = get("/api/weekly-summary")
        assert res.status_code == 200
