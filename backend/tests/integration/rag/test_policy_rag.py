"""
Integration: policy RAG — answer quality, source structure, role access.

Hits the live backend with a real LLM. Requires policies ingested.
"""
import requests
import pytest
from tests.integration.config import BASE_URL


def _chat_policy(message: str, token: str, timeout: int = 30) -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat/policy",
        json={"message": message},
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("success") is True, f"success=False: {body}"
    return body["data"]


class TestPolicyResponseStructure:
    def test_answer_and_sources_present(self, cc_admin_token):
        data = _chat_policy("What is the leave policy?", cc_admin_token)
        assert "answer" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_answer_is_substantive(self, cc_admin_token):
        data = _chat_policy("What is the leave policy?", cc_admin_token)
        assert len(data["answer"].strip()) > 20, "Answer too short"

    def test_each_source_has_title_category_filename(self, cc_admin_token):
        data = _chat_policy("What is the WFH policy?", cc_admin_token)
        for src in data["sources"]:
            assert "title" in src, f"Missing title in source: {src}"
            assert "category" in src
            assert "filename" in src


class TestPolicyAccessAllRoles:
    def test_employee_gets_policy_answer(self, cc_employee_token):
        data = _chat_policy("How many casual leaves do I get?", cc_employee_token)
        assert len(data["answer"].strip()) > 10

    def test_manager_gets_policy_answer(self, cc_manager_token):
        data = _chat_policy("What is the WFH policy?", cc_manager_token)
        assert len(data["answer"].strip()) > 10

    def test_admin_gets_policy_answer(self, cc_admin_token):
        data = _chat_policy("Explain the code of conduct.", cc_admin_token)
        assert len(data["answer"].strip()) > 10


class TestPolicyAuthEnforcement:
    def test_no_token_rejected(self):
        resp = requests.post(f"{BASE_URL}/api/v1/chat/policy", json={"message": "x"}, timeout=10)
        assert resp.status_code == 401

    def test_bad_token_rejected(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/chat/policy",
            json={"message": "x"},
            headers={"Authorization": "Bearer garbage"},
            timeout=10,
        )
        assert resp.status_code == 401
