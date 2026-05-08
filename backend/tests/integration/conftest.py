"""
Live-backend fixtures for integration tests.

Uses cc_ prefix to avoid colliding with the in-memory fixtures in tests/conftest.py
which are used by the mocked integration tests (test_admin_endpoints, test_chat_endpoints).
"""
import pytest
import requests
from tests.integration.config import BASE_URL, USERS


def _login(role: str) -> str:
    creds = USERS[role]
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": creds["email"], "password": creds["password"]},
        timeout=10,
    )
    assert resp.status_code == 200, f"Login failed for {role}: {resp.text}"
    data = resp.json()
    assert data["success"] is True, f"Login not successful: {data}"
    return data["data"]["access_token"]


@pytest.fixture(scope="session")
def cc_admin_token() -> str:
    return _login("admin")


@pytest.fixture(scope="session")
def cc_manager_token() -> str:
    return _login("manager")


@pytest.fixture(scope="session")
def cc_employee_token() -> str:
    return _login("employee")
