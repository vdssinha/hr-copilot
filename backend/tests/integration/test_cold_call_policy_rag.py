"""Cold-call: policy RAG endpoint tests (live backend, real LLM)."""
import requests
import pytest
from tests.integration.cold_call_config import BASE_URL
from tests.integration.cold_call_conftest import (  # noqa: F401
    cc_admin_token, cc_manager_token, cc_employee_token,
)


def _policy(message: str, token: str, timeout: int = 30) -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/policy",
        json={"message": message},
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("success") is True, f"success=False: {body}"
    return body["data"]


class TestPolicyRagStructure:
    def test_response_has_answer_and_sources(self, cc_admin_token):
        data = _policy("What is the leave policy?", cc_admin_token)
        assert "answer" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_answer_is_non_empty(self, cc_admin_token):
        data = _policy("What is the leave policy?", cc_admin_token)
        assert len(data["answer"].strip()) > 20

    def test_sources_have_expected_fields(self, cc_admin_token):
        data = _policy("What is the leave policy?", cc_admin_token)
        for src in data["sources"]:
            assert "title" in src
            assert "category" in src
            assert "filename" in src


class TestPolicyRagAllRoles:
    def test_employee_gets_answer(self, cc_employee_token):
        data = _policy("How many casual leaves do I get?", cc_employee_token)
        assert len(data["answer"].strip()) > 10

    def test_manager_gets_answer(self, cc_manager_token):
        data = _policy("What is the WFH policy?", cc_manager_token)
        assert len(data["answer"].strip()) > 10

    def test_admin_gets_answer(self, cc_admin_token):
        data = _policy("Explain the code of conduct.", cc_admin_token)
        assert len(data["answer"].strip()) > 10


class TestPolicyRagAuth:
    def test_no_token_rejected(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/policy",
            json={"message": "test"},
            timeout=10,
        )
        assert resp.status_code == 401

    def test_bad_token_rejected(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/policy",
            json={"message": "test"},
            headers={"Authorization": "Bearer garbage"},
            timeout=10,
        )
        assert resp.status_code == 401
