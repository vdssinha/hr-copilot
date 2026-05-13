"""
Unit tests for chat conversation history — context.build_history_block
and the history injection path in policy_rag + sql_agent.

These tests are pure-unit: no DB, no HTTP, no LLM calls.
"""
import json
import pytest
from unittest.mock import MagicMock, patch

from app.services.ai.core.memory.context import build_history_block
from app.services.ai import factory as ai_factory


# ─── build_history_block ──────────────────────────────────────────────────────

def test_empty_history_returns_empty_string():
    assert build_history_block([]) == ""


def test_none_history_returns_empty_string():
    # callers pass `history or []`; test the function directly with []
    assert build_history_block([]) == ""


def test_single_turn_formatted_correctly():
    history = [
        {"role": "user",      "content": "How many sick leaves do I get?"},
        {"role": "assistant", "content": "You get 12 sick days per year."},
    ]
    block = build_history_block(history)
    assert "User: How many sick leaves do I get?" in block
    assert "Assistant: You get 12 sick days per year." in block
    assert "Prior conversation" in block
    assert "Current message:" in block


def test_history_block_trims_to_max_turns():
    from app.core.config import AI_CONTEXT_TURNS
    # Use unique non-overlapping content to avoid substring false-positives
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"XMSG_{i:04d}_X"}
        for i in range(20)
    ]
    block = build_history_block(history)
    kept    = history[-(AI_CONTEXT_TURNS * 2):]
    dropped = history[:-(AI_CONTEXT_TURNS * 2)]
    for msg in kept:
        assert msg["content"] in block, f"Expected kept message '{msg['content']}' in block"
    for msg in dropped:
        assert msg["content"] not in block, f"Dropped message '{msg['content']}' leaked into block"


def test_history_block_custom_max_turns():
    history = [{"role": "user", "content": f"q{i}"} for i in range(10)]
    block = build_history_block(history, max_turns=2)
    assert "q8" in block
    assert "q9" in block
    assert "q0" not in block


def test_history_block_single_message():
    history = [{"role": "user", "content": "Only one message"}]
    block = build_history_block(history)
    assert "Only one message" in block


def test_history_block_missing_role_defaults_to_user():
    history = [{"content": "No role field"}]
    block = build_history_block(history)
    assert "User: No role field" in block


def test_history_block_missing_content_defaults_empty():
    history = [{"role": "assistant"}]
    block = build_history_block(history)
    assert "Assistant: " in block


# ─── history injection into policy_rag prompt ────────────────────────────────

def test_policy_rag_injects_history_into_llm_prompt():
    """History block must appear in the prompt sent to the LLM (direct service call)."""
    from app.services.ai.agents import policy_rag as _policy_rag
    from app.models.employee import EmployeeRole
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db.base import Base
    import app.models  # noqa — register models

    # Stand-alone in-memory DB (avoids fixture-scope conflicts)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    prior_turn = [
        {"role": "user",      "content": "What is the leave policy?"},
        {"role": "assistant", "content": "You have 12 sick days per year."},
    ]

    captured_prompts: list[str] = []
    fake_llm = MagicMock()
    def capture_generate(prompt, **kw):
        captured_prompts.append(prompt)
        return "You also have 10 casual leave days."
    fake_llm.generate.side_effect = capture_generate

    fake_embedder = MagicMock()
    fake_embedder.embed_query.return_value = [0.1] * 768
    fake_embedder.embed.side_effect = lambda texts: [[0.1] * 768 for _ in texts]

    fake_doc = MagicMock()
    fake_doc.content = "Casual leave: 10 days."
    fake_doc.metadata = {"title": "Leave Policy", "category": "HR", "filename": "leave.md"}
    fake_vs = MagicMock()
    fake_vs.count.return_value = 3
    fake_vs.similarity_search.return_value = [(fake_doc, 0.5)]

    with (
        patch.object(ai_factory, "get_llm_provider", return_value=fake_llm),
        patch.object(ai_factory, "get_embedder",     return_value=fake_embedder),
        patch.object(ai_factory, "get_vector_store", return_value=fake_vs),
        patch.object(_policy_rag, "_get_accessible_categories", return_value=["LEAVE", "GENERAL"]),
    ):
        result = _policy_rag.answer_policy_question(
            db,
            "And how many casual leaves?",
            user_role=EmployeeRole.EMPLOYEE,
            history=prior_turn,
        )

    assert len(captured_prompts) >= 1, "LLM generate() was never called"
    combined = " ".join(captured_prompts)
    assert "What is the leave policy?" in combined, \
        "Prior-turn user message missing from LLM prompt"
    assert result["answer"] == "You also have 10 casual leave days."


def test_policy_rag_works_without_history(client, employee_token):
    """Omitting history (backward-compat) must not error."""
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "12 sick days."

    fake_embedder = MagicMock()
    fake_embedder.embed_query.return_value = [0.1] * 768
    fake_embedder.embed.side_effect = lambda texts: [[0.1] * 768 for _ in texts]

    fake_doc = MagicMock()
    fake_doc.content = "Sick leave: 12 days."
    fake_doc.metadata = {"title": "Leave Policy", "category": "HR", "filename": "leave.md"}
    fake_vs = MagicMock()
    fake_vs.count.return_value = 1
    fake_vs.similarity_search.return_value = [(fake_doc, 0.5)]

    with (
        patch.object(ai_factory, "get_llm_provider", return_value=fake_llm),
        patch.object(ai_factory, "get_embedder",     return_value=fake_embedder),
        patch.object(ai_factory, "get_vector_store", return_value=fake_vs),
    ):
        resp = client.post(
            "/api/v1/chat/policy",
            json={"message": "How many sick leaves do I get?"},
            headers={"Authorization": f"Bearer {employee_token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ─── history injection into sql_agent prompt ─────────────────────────────────

def test_sql_agent_injects_history_into_prompt(client, admin_token):
    """Prior-turn history must be prepended to the NL→SQL prompt."""
    prior_turn = [
        {"role": "user",      "content": "Show all ongoing projects"},
        {"role": "assistant", "content": "Here are the ongoing projects: Alpha, Beta."},
    ]

    captured_prompts: list[str] = []

    def capture_generate(prompt, **kw):
        captured_prompts.append(prompt)
        return "SELECT name FROM projects WHERE status = 'ONGOING'"
    fake_llm = MagicMock()
    fake_llm.generate.side_effect = capture_generate

    with patch.object(ai_factory, "get_llm_provider", return_value=fake_llm):
        resp = client.post(
            "/api/v1/chat/sql",
            json={
                "message": "Which one of those has the most employees?",
                "history": prior_turn,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    assert len(captured_prompts) >= 1
    combined = " ".join(captured_prompts)
    assert "Show all ongoing projects" in combined


def test_sql_agent_empty_history_accepted(client, admin_token):
    """Empty history list must not break the sql endpoint."""
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "SELECT name FROM projects WHERE status = 'ONGOING'"

    with patch.object(ai_factory, "get_llm_provider", return_value=fake_llm):
        resp = client.post(
            "/api/v1/chat/sql",
            json={"message": "Show ongoing projects", "history": []},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ─── history accepted by actions endpoint ────────────────────────────────────

def test_actions_endpoint_accepts_history(client, employee_token, db_session, seed_employees):
    """Actions endpoint must accept history without error."""
    prior_turn = [
        {"role": "user",      "content": "What leave types do we have?"},
        {"role": "assistant", "content": "SICK, CASUAL, ANNUAL, MATERNITY, PATERNITY."},
    ]
    llm_response = json.dumps({
        "action": "apply_leave",
        "params": {
            "leave_type": "CASUAL",
            "start_date": "2026-08-01",
            "end_date": "2026-08-01",
            "reason": "Personal",
            "is_half_day": False,
            "half_day_period": None,
        },
        "cannot_do_reason": None,
    })
    fake_llm = MagicMock()
    fake_llm.generate.side_effect = [llm_response, "Your casual leave has been submitted."]

    with patch.object(ai_factory, "get_llm_provider", return_value=fake_llm):
        resp = client.post(
            "/api/v1/chat/actions",
            json={
                "message": "Apply casual leave for Aug 1",
                "history": prior_turn,
            },
            headers={"Authorization": f"Bearer {employee_token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["action"] == "apply_leave"


# ─── history trimming preserves most-recent turns ────────────────────────────

def test_history_block_preserves_most_recent_turns():
    """When history exceeds max_turns, newest messages must be retained."""
    history = [
        {"role": "user",      "content": f"old question {i}"}
        for i in range(20)
    ] + [
        {"role": "user",      "content": "NEWEST question"},
        {"role": "assistant", "content": "NEWEST answer"},
    ]
    block = build_history_block(history, max_turns=3)
    assert "NEWEST question" in block
    assert "NEWEST answer" in block
    assert "old question 0" not in block
