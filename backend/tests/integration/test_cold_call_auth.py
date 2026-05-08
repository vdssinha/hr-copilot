"""Cold-call: authentication endpoint tests (live backend, no mocks)."""
import requests
import pytest
from tests.integration.cold_call_config import BASE_URL, USERS
from tests.integration.cold_call_conftest import cc_employee_token  # noqa: F401


def _login(email: str, password: str) -> requests.Response:
    return requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )


class TestLogin:
    def test_health_endpoint(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_admin_login_succeeds(self):
        u = USERS["admin"]
        resp = _login(u["email"], u["password"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["role"] == "ADMIN"
        assert data["data"]["name"] == u["name"]
        assert "access_token" in data["data"]

    def test_manager_login_succeeds(self):
        u = USERS["manager"]
        resp = _login(u["email"], u["password"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["role"] == "MANAGER"
        assert data["data"]["name"] == u["name"]

    def test_employee_login_succeeds(self):
        u = USERS["employee"]
        resp = _login(u["email"], u["password"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["role"] == "EMPLOYEE"
        assert data["data"]["name"] == u["name"]

    def test_wrong_password_returns_401(self):
        u = USERS["employee"]
        resp = _login(u["email"], "wrong-password")
        assert resp.status_code == 401

    def test_unknown_email_returns_401(self):
        resp = _login("nobody@example.com", "irrelevant")
        assert resp.status_code == 401

    def test_token_is_usable(self, cc_employee_token):
        """Token from fixture works on protected endpoints (not 401/403)."""
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/policy",
            json={"message": "test"},
            headers={"Authorization": f"Bearer {cc_employee_token}"},
            timeout=60,
        )
        assert resp.status_code not in (401, 403)

    def test_no_token_returns_401(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/policy",
            json={"message": "test"},
            timeout=10,
        )
        assert resp.status_code == 401

    def test_garbage_token_returns_401(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/policy",
            json={"message": "test"},
            headers={"Authorization": "Bearer not.a.real.token"},
            timeout=10,
        )
        assert resp.status_code == 401
