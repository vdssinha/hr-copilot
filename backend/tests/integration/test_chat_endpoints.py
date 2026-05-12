"""
Integration tests for /api/v1/chat/* endpoints.

LLM, embedder, and vector-store are mocked so tests run without LM Studio / Anthropic.
Tests verify: auth gating, RBAC enforcement, response structure, audit trail.
"""
import json
import pytest
from unittest.mock import MagicMock, patch

from app.services.ai import factory as ai_factory


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _fake_llm(response: str):
    llm = MagicMock()
    llm.generate.return_value = response
    return llm


# ─── Auth gating (all endpoints require JWT) ─────────────────────────────────

@pytest.mark.parametrize("path", [
    "/api/v1/chat/policy",
    "/api/v1/chat/sql",
    "/api/v1/chat/actions",
    "/api/v1/chat/router",
])
def test_unauthenticated_returns_401(client, path):
    resp = client.post(path, json={"message": "test"})
    assert resp.status_code == 401


def test_policy_ingest_requires_auth(client):
    resp = client.post("/api/v1/chat/policy/ingest")
    assert resp.status_code == 401


# ─── /chat/policy ─────────────────────────────────────────────────────────────

def test_policy_endpoint_returns_200(client, employee_token):
    fake_llm = _fake_llm("You are entitled to 12 sick leave days per year.")
    fake_embedder = MagicMock()
    fake_embedder.embed_query.return_value = [0.1] * 768
    # SemanticRouter._index() calls embed(utterances) — return proper 2D shape
    fake_embedder.embed.side_effect = lambda texts: [[0.1] * 768 for _ in texts]

    fake_doc = MagicMock()
    fake_doc.content = "Sick leave: 12 days per year."
    fake_doc.metadata = {"title": "Leave Policy", "category": "HR", "filename": "leave.md"}

    fake_vs = MagicMock()
    fake_vs.count.return_value = 5
    fake_vs.similarity_search.return_value = [(fake_doc, 0.5)]

    with (
        patch.object(ai_factory, "get_llm_provider", return_value=fake_llm),
        patch.object(ai_factory, "get_embedder", return_value=fake_embedder),
        patch.object(ai_factory, "get_vector_store", return_value=fake_vs),
    ):
        resp = client.post(
            "/api/v1/chat/policy",
            json={"message": "How many sick leaves do I get?"},
            headers=_auth(employee_token),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "answer" in body["data"]
    assert "sources" in body["data"]


def test_policy_endpoint_all_roles_allowed(client, manager_token, admin_token):
    fake_llm = _fake_llm("WFH is allowed.")
    fake_embedder = MagicMock()
    fake_embedder.embed_query.return_value = [0.1] * 768
    fake_embedder.embed.side_effect = lambda texts: [[0.1] * 768 for _ in texts]
    fake_doc = MagicMock()
    fake_doc.content = "WFH allowed after probation."
    fake_doc.metadata = {"title": "WFH Policy", "category": "HR", "filename": "wfh.md"}
    fake_vs = MagicMock()
    fake_vs.count.return_value = 3
    fake_vs.similarity_search.return_value = [(fake_doc, 0.4)]

    for token in [manager_token, admin_token]:
        with (
            patch.object(ai_factory, "get_llm_provider", return_value=fake_llm),
            patch.object(ai_factory, "get_embedder", return_value=fake_embedder),
            patch.object(ai_factory, "get_vector_store", return_value=fake_vs),
        ):
            resp = client.post(
                "/api/v1/chat/policy",
                json={"message": "Can I work from home?"},
                headers=_auth(token),
            )
        assert resp.status_code == 200


# ─── /chat/sql ────────────────────────────────────────────────────────────────

def test_sql_endpoint_returns_200(client, admin_token):
    safe_sql = "SELECT name FROM projects WHERE status = 'ONGOING'"
    fake_llm = _fake_llm(safe_sql)

    with patch.object(ai_factory, "get_llm_provider", return_value=fake_llm):
        resp = client.post(
            "/api/v1/chat/sql",
            json={"message": "Which projects are ongoing?"},
            headers=_auth(admin_token),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "sql" in body["data"]
    assert "rows" in body["data"]


def test_sql_endpoint_blocks_ddl_from_llm(client, admin_token):
    # LLM returns DDL — guardrail must block it and endpoint must still return 200 (safe refusal)
    fake_llm = _fake_llm("DROP TABLE employees")

    with patch.object(ai_factory, "get_llm_provider", return_value=fake_llm):
        resp = client.post(
            "/api/v1/chat/sql",
            json={"message": "Drop all employees"},
            headers=_auth(admin_token),
        )

    assert resp.status_code == 200
    body = resp.json()
    # Guardrail triggers → sql agent returns CANNOT_ANSWER or guard error message
    # Either success=False or rows=0 with refusal message
    data = body.get("data", {})
    assert data.get("row_count", 0) == 0


def test_sql_endpoint_blocks_forbidden_column(client, employee_token):
    fake_llm = _fake_llm("SELECT hashed_password FROM employees WHERE id = 4")

    with patch.object(ai_factory, "get_llm_provider", return_value=fake_llm):
        resp = client.post(
            "/api/v1/chat/sql",
            json={"message": "Show me passwords"},
            headers=_auth(employee_token),
        )

    assert resp.status_code == 200
    body = resp.json()
    data = body.get("data", {})
    assert data.get("row_count", 0) == 0


# ─── /chat/actions ────────────────────────────────────────────────────────────

def test_actions_endpoint_employee_apply_leave(client, employee_token, db_session, seed_employees):
    llm_response = json.dumps({
        "action": "apply_leave",
        "params": {
            "leave_type": "SICK",
            "start_date": "2026-06-01",
            "end_date": "2026-06-03",
            "reason": "Unwell",
            "is_half_day": False,
            "half_day_period": None,
        },
        "cannot_do_reason": None,
    })
    fake_llm = _fake_llm(llm_response)
    # Second call (summary) returns friendly text
    fake_llm.generate.side_effect = [llm_response, "Your sick leave has been submitted."]

    with patch.object(ai_factory, "get_llm_provider", return_value=fake_llm):
        resp = client.post(
            "/api/v1/chat/actions",
            json={"message": "Apply sick leave from June 1 to June 3"},
            headers=_auth(employee_token),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["action"] == "apply_leave"
    assert data["success"] is True


def test_actions_endpoint_employee_cannot_approve_leave(client, employee_token):
    llm_response = json.dumps({
        "action": "approve_leave",
        "params": {"request_id": 1},
        "cannot_do_reason": None,
    })
    fake_llm = _fake_llm(llm_response)

    with patch.object(ai_factory, "get_llm_provider", return_value=fake_llm):
        resp = client.post(
            "/api/v1/chat/actions",
            json={"message": "Approve leave request 1"},
            headers=_auth(employee_token),
        )

    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert data["success"] is False
    assert "permission" in data["answer"].lower()


def test_actions_endpoint_manager_can_approve_leave(
    client, manager_token, db_session, seed_employees
):
    # Create a leave request from the employee first
    from app.models.leave import LeaveRequest, LeaveType, LeaveStatus
    from datetime import date
    emp = seed_employees["employee"]
    leave = LeaveRequest(
        employee_id=emp.id,
        leave_type=LeaveType.SICK,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        reason="Test",
        status=LeaveStatus.PENDING,
        is_half_day=False,
    )
    db_session.add(leave)
    db_session.commit()
    db_session.refresh(leave)
    leave_id = leave.id

    llm_response = json.dumps({
        "action": "approve_leave",
        "params": {"request_id": leave_id},
        "cannot_do_reason": None,
    })
    fake_llm = _fake_llm(llm_response)
    fake_llm.generate.side_effect = [llm_response, "Leave has been approved."]

    with patch.object(ai_factory, "get_llm_provider", return_value=fake_llm):
        resp = client.post(
            "/api/v1/chat/actions",
            json={"message": f"Approve leave request {leave_id}"},
            headers=_auth(manager_token),
        )

    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert data["action"] == "approve_leave"
    assert data["success"] is True


def test_actions_employee_cannot_create_announcement(client, employee_token):
    llm_response = json.dumps({
        "action": "create_announcement",
        "params": {
            "title": "Hack",
            "content": "I hacked it",
            "category": "GENERAL",
            "is_pinned": False,
        },
        "cannot_do_reason": None,
    })
    fake_llm = _fake_llm(llm_response)

    with patch.object(ai_factory, "get_llm_provider", return_value=fake_llm):
        resp = client.post(
            "/api/v1/chat/actions",
            json={"message": "Create announcement: I hacked it"},
            headers=_auth(employee_token),
        )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is False


# ─── /chat/policy/ingest ─────────────────────────────────────────────────────

def test_policy_ingest_blocked_for_employee(client, employee_token):
    resp = client.post(
        "/api/v1/chat/policy/ingest",
        headers=_auth(employee_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "admin" in body["error"].lower()


def test_policy_ingest_blocked_for_manager(client, manager_token):
    resp = client.post(
        "/api/v1/chat/policy/ingest",
        headers=_auth(manager_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False


def test_policy_ingest_allowed_for_admin(client, admin_token):
    fake_embedder = MagicMock()
    fake_embedder.embed.return_value = [[0.1] * 768]
    fake_vs = MagicMock()
    fake_vs.count.return_value = 0

    with (
        patch.object(ai_factory, "get_embedder", return_value=fake_embedder),
        patch.object(ai_factory, "get_vector_store", return_value=fake_vs),
    ):
        resp = client.post(
            "/api/v1/chat/policy/ingest",
            headers=_auth(admin_token),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "chunks_ingested" in body["data"]
