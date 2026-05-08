"""
Cold-call fixtures — live backend tokens.

Named cc_* to avoid conflicting with the in-memory tokens defined in tests/conftest.py
which are used by the mocked integration tests (test_chat_endpoints, test_admin_endpoints).

Import in each cold_call test file:
    from tests.integration.cold_call_conftest import cc_admin_token, cc_manager_token, cc_employee_token
"""
import pytest
import requests
from tests.integration.cold_call_config import BASE_URL, USERS


def _cc_login(role: str) -> str:
    creds = USERS[role]
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": creds["email"], "password": creds["password"]},
        timeout=10,
    )
    assert resp.status_code == 200, f"Login failed for {role}: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    return data["data"]["access_token"]


@pytest.fixture(scope="session")
def cc_admin_token() -> str:
    return _cc_login("admin")


@pytest.fixture(scope="session")
def cc_manager_token() -> str:
    return _cc_login("manager")


@pytest.fixture(scope="session")
def cc_employee_token() -> str:
    return _cc_login("employee")


@pytest.fixture(scope="session")
def cc_base_url() -> str:
    return BASE_URL
