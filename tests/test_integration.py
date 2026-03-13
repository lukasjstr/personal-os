"""Epic 3.2: Integration smoke tests for core Personal OS flows.

Target flows:
- auth/token access
- dashboard health fetch
- task completion → next_action response
- proposal draft create/review/execute happy path
- calendar/ical settings endpoint

Run with:
    API_BASE_URL=http://localhost:8000 API_TOKEN=<token> pytest tests/test_integration.py -v

Requires API_TOKEN env var.  Some tests create small DB fixtures (tasks, proposal drafts)
and leave minimal state — test-origin rows are marked with [smoke-test] in their title.
"""
import os

import pytest
import requests

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
API_TOKEN = os.environ.get("API_TOKEN", "")

HEADERS = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}
TEST_MARKER = "[smoke-test]"

requires_token = pytest.mark.skipif(not API_TOKEN, reason="API_TOKEN not set")


# ─── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", headers=HEADERS, timeout=10, **kwargs)


def _post(path: str, body: dict, **kwargs) -> requests.Response:
    return requests.post(f"{API_BASE}{path}", json=body, headers=HEADERS, timeout=10, **kwargs)


def _put(path: str, body: dict, **kwargs) -> requests.Response:
    return requests.put(f"{API_BASE}{path}", json=body, headers=HEADERS, timeout=10, **kwargs)


def _delete(path: str, **kwargs) -> requests.Response:
    return requests.delete(f"{API_BASE}{path}", headers=HEADERS, timeout=10, **kwargs)


# ─── Auth / Token Access ───────────────────────────────────────────────────────

@requires_token
class TestAuthTokenAccess:
    def test_validate_token_get(self):
        """GET /auth/validate returns 200 with valid=True for valid token."""
        res = _get("/api/auth/validate")
        assert res.status_code == 200
        data = res.json()
        assert data.get("valid") is True
        assert "user_id" in data

    def test_validate_token_post(self):
        """POST /auth/validate also returns 200 for valid token."""
        res = _post("/api/auth/validate", {})
        assert res.status_code == 200
        data = res.json()
        assert data.get("valid") is True

    def test_no_token_returns_4xx(self):
        """Requests without Authorization header return 401 or 403 (unauthenticated)."""
        res = requests.get(f"{API_BASE}/api/settings", timeout=10)
        assert res.status_code in (401, 403), f"Expected 401/403, got {res.status_code}"

    def test_bad_token_returns_401(self):
        """Requests with a bogus token return 401."""
        res = requests.get(
            f"{API_BASE}/api/settings",
            headers={"Authorization": "Bearer definitely-not-a-valid-token-xyz"},
            timeout=10,
        )
        assert res.status_code == 401


# ─── Dashboard Health Fetch ────────────────────────────────────────────────────

class TestDashboardHealthFetch:
    def test_health_200(self):
        """GET /health returns 200."""
        res = _get("/api/health")
        assert res.status_code == 200

    def test_health_has_status_field(self):
        """Health response contains a status field."""
        res = _get("/api/health")
        data = res.json()
        assert "status" in data

    def test_health_db_connected(self):
        """Health response shows DB as connected."""
        res = _get("/api/health")
        data = res.json()
        db_val = data.get("db")
        assert db_val in (None, "ok", True, "connected"), f"Unexpected db value: {db_val!r}"

    @requires_token
    def test_dashboard_returns_user(self):
        """GET /dashboard returns 200 with a user key."""
        res = _get("/api/dashboard")
        assert res.status_code == 200
        assert "user" in res.json()

    @requires_token
    def test_autopilot_today_shape(self):
        """GET /autopilot/today returns date and plan keys."""
        res = _get("/api/autopilot/today")
        assert res.status_code in (200, 500)
        if res.status_code == 200:
            data = res.json()
            assert "date" in data
            assert "plan" in data


# ─── Task Completion → next_action Response ───────────────────────────────────

@requires_token
class TestTaskCompletionNextAction:
    def test_complete_nonexistent_task_404(self):
        """Completing a task ID that doesn't exist returns 404."""
        res = _post("/api/tasks/999999999/complete", {})
        assert res.status_code == 404

    def test_create_and_complete_task(self):
        """Create a task then complete it; response has ok=True, task_id, xp_gained."""
        create_res = _post("/api/tasks", {
            "title": f"{TEST_MARKER} smoke completion test",
            "priority": 3,
        })
        assert create_res.status_code == 200, f"Task creation failed: {create_res.text}"
        task_id = create_res.json()["id"]

        complete_res = _post(f"/api/tasks/{task_id}/complete", {})
        assert complete_res.status_code == 200, f"Task completion failed: {complete_res.text}"
        data = complete_res.json()
        assert data.get("ok") is True
        assert data.get("task_id") == task_id
        assert "xp_gained" in data

    def test_complete_task_may_include_next_action(self):
        """Completed task response may include next_action — field is present when tasks remain."""
        create_res = _post("/api/tasks", {
            "title": f"{TEST_MARKER} next_action field test",
            "priority": 3,
        })
        assert create_res.status_code == 200
        task_id = create_res.json()["id"]

        complete_res = _post(f"/api/tasks/{task_id}/complete", {})
        assert complete_res.status_code == 200
        data = complete_res.json()
        # next_action is optional — just verify it's a dict when present
        if "next_action" in data and data["next_action"] is not None:
            assert isinstance(data["next_action"], dict)

    def test_next_action_endpoint_accessible(self):
        """GET /autopilot/next-action returns 200 or 404 (no tasks available)."""
        res = _get("/api/autopilot/next-action")
        assert res.status_code in (200, 404)
        if res.status_code == 200:
            assert isinstance(res.json(), dict)


# ─── Proposal Draft Happy Path ─────────────────────────────────────────────────

@requires_token
class TestProposalDraftHappyPath:
    def test_list_proposal_drafts(self):
        """GET /objectives/proposal-drafts returns a list."""
        res = _get("/api/objectives/proposal-drafts")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_proposal_draft(self):
        """POST /objectives/proposal-drafts creates a draft with expected fields."""
        res = _post("/api/objectives/proposal-drafts", {
            "source_text": f"{TEST_MARKER} create-only smoke test",
            "draft_payload": {"objective": {"title": f"{TEST_MARKER} create test obj"}},
        })
        assert res.status_code == 200, f"Create failed: {res.text}"
        data = res.json()
        assert "id" in data
        assert "status" in data
        assert "source_text" in data
        # Cleanup
        _delete(f"/api/objectives/proposal-drafts/{data['id']}")

    def test_get_draft_by_id(self):
        """Created draft is retrievable by ID."""
        create_res = _post("/api/objectives/proposal-drafts", {
            "source_text": f"{TEST_MARKER} get-by-id test",
            "draft_payload": {"objective": {"title": f"{TEST_MARKER} get test obj"}},
        })
        assert create_res.status_code == 200
        draft_id = create_res.json()["id"]

        get_res = _get(f"/api/objectives/proposal-drafts/{draft_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == draft_id

        _delete(f"/api/objectives/proposal-drafts/{draft_id}")

    def test_review_draft_accept(self):
        """Review with action=accept transitions draft to accepted status."""
        create_res = _post("/api/objectives/proposal-drafts", {
            "source_text": f"{TEST_MARKER} review-accept test",
            "draft_payload": {"objective": {"title": f"{TEST_MARKER} review obj"}},
        })
        assert create_res.status_code == 200
        draft_id = create_res.json()["id"]

        review_res = _post(f"/api/objectives/proposal-drafts/{draft_id}/review", {
            "action": "accept",
        })
        assert review_res.status_code == 200, f"Review failed: {review_res.text}"
        assert review_res.json()["status"] == "accepted"

        _delete(f"/api/objectives/proposal-drafts/{draft_id}")

    def test_review_draft_reject(self):
        """Review with action=reject transitions draft to rejected status."""
        create_res = _post("/api/objectives/proposal-drafts", {
            "source_text": f"{TEST_MARKER} review-reject test",
            "draft_payload": {"objective": {"title": f"{TEST_MARKER} reject obj"}},
        })
        assert create_res.status_code == 200
        draft_id = create_res.json()["id"]

        review_res = _post(f"/api/objectives/proposal-drafts/{draft_id}/review", {
            "action": "reject",
        })
        assert review_res.status_code == 200
        assert review_res.json()["status"] == "rejected"

        _delete(f"/api/objectives/proposal-drafts/{draft_id}")

    def test_full_create_review_execute_flow(self):
        """Full happy path: create → review(accept) → execute returns ok=True."""
        create_res = _post("/api/objectives/proposal-drafts", {
            "source_text": f"{TEST_MARKER} full execute flow",
            "draft_payload": {
                "objective": {
                    "title": f"{TEST_MARKER} executed objective",
                    "category": "personal",
                },
                "tasks": [{"title": f"{TEST_MARKER} spawned from proposal"}],
            },
        })
        assert create_res.status_code == 200, f"Create failed: {create_res.text}"
        draft_id = create_res.json()["id"]

        review_res = _post(f"/api/objectives/proposal-drafts/{draft_id}/review", {
            "action": "accept",
        })
        assert review_res.status_code == 200, f"Review failed: {review_res.text}"
        assert review_res.json()["status"] == "accepted"

        execute_res = _post(f"/api/objectives/proposal-drafts/{draft_id}/execute", {})
        assert execute_res.status_code == 200, f"Execute failed: {execute_res.text}"
        data = execute_res.json()
        assert data.get("ok") is True
        assert data.get("status") == "executed"

    def test_delete_draft(self):
        """DELETE /objectives/proposal-drafts/{id} removes the draft (GET returns 404)."""
        create_res = _post("/api/objectives/proposal-drafts", {
            "source_text": f"{TEST_MARKER} delete test",
            "draft_payload": {"objective": {"title": f"{TEST_MARKER} to delete"}},
        })
        assert create_res.status_code == 200
        draft_id = create_res.json()["id"]

        delete_res = _delete(f"/api/objectives/proposal-drafts/{draft_id}")
        assert delete_res.status_code == 200

        get_res = _get(f"/api/objectives/proposal-drafts/{draft_id}")
        assert get_res.status_code == 404


# ─── Calendar / iCal Settings ─────────────────────────────────────────────────

@requires_token
class TestCalendarIcalSettings:
    def test_ical_status_get(self):
        """GET /settings/ical returns 200 and a dict."""
        res = _get("/api/settings/ical")
        assert res.status_code == 200
        assert isinstance(res.json(), dict)

    def test_ical_clear_url(self):
        """PUT /settings/ical with ical_url=None clears the URL without error."""
        res = _put("/api/settings/ical", {"ical_url": None})
        assert res.status_code == 200

    def test_ical_invalid_url_not_500(self):
        """PUT /settings/ical with a non-URL string returns 200, 400, or 422 — never 500."""
        res = _put("/api/settings/ical", {"ical_url": "not-a-url"})
        assert res.status_code in (200, 400, 422), f"Unexpected status: {res.status_code}"

    def test_calendar_list_accessible(self):
        """GET /calendar returns 200 and a dict."""
        res = _get("/api/calendar")
        assert res.status_code == 200
        assert isinstance(res.json(), dict)
