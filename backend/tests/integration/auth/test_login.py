"""
Integration: authentication — login, token issuance, 401 enforcement.

Hits the live backend. No mocks.
"""
import requests
import pytest
from tests.integration.config import BASE_URL, USERS


def _post_login(email: str, password: str) -> requests.Response:
    return requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )


class TestHealthCheck:
    def test_backend_is_up(self):
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestLoginSuccess:
    def test_admin_receives_token_and_role(self):
        u = USERS["admin"]
        resp = _post_login(u["email"], u["password"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["role"] == "ADMIN"
        assert data["data"]["name"] == u["name"]
        assert len(data["data"]["access_token"]) > 20

    def test_manager_receives_correct_role(self):
        u = USERS["manager"]
        resp = _post_login(u["email"], u["password"])
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "MANAGER"

    def test_employee_receives_correct_role(self):
        u = USERS["employee"]
        resp = _post_login(u["email"], u["password"])
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "EMPLOYEE"

    def test_response_includes_user_id_and_name(self):
        u = USERS["admin"]
        data = _post_login(u["email"], u["password"]).json()["data"]
        assert "user_id" in data
        assert data["name"] == u["name"]


class TestLoginFailure:
    def test_wrong_password_returns_401(self):
        resp = _post_login(USERS["employee"]["email"], "wrong-password")
        assert resp.status_code == 401

    def test_unknown_email_returns_401(self):
        resp = _post_login("nobody@example.com", "irrelevant")
        assert resp.status_code == 401


class TestTokenEnforcement:
    def test_missing_token_returns_401(self):
        resp = requests.post(f"{BASE_URL}/api/v1/chat/policy", json={"message": "x"}, timeout=10)
        assert resp.status_code == 401

    def test_garbage_token_returns_401(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/policy",
            json={"message": "x"},
            headers={"Authorization": "Bearer not.a.real.token"},
            timeout=10,
        )
        assert resp.status_code == 401

    def test_valid_token_reaches_endpoint(self, cc_employee_token):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/policy",
            json={"message": "x"},
            headers={"Authorization": f"Bearer {cc_employee_token}"},
            timeout=60,
        )
        assert resp.status_code not in (401, 403)
