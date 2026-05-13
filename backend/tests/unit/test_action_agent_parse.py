"""
Unit tests for _parse_llm_json — the JSON extraction helper in action_agent.
Tests the markdown-fence stripping, surrounding-text extraction, and error paths.
"""
import json
import pytest
from app.services.ai.agents.action_agent import _parse_llm_json


def test_clean_json():
    raw = '{"action": "apply_leave", "params": {}, "cannot_do_reason": null}'
    result = _parse_llm_json(raw)
    assert result["action"] == "apply_leave"


def test_json_with_markdown_fence():
    raw = '```json\n{"action": "create_ticket", "params": {}, "cannot_do_reason": null}\n```'
    result = _parse_llm_json(raw)
    assert result["action"] == "create_ticket"


def test_json_with_plain_code_fence():
    raw = '```\n{"action": "UNKNOWN", "params": {}, "cannot_do_reason": null}\n```'
    result = _parse_llm_json(raw)
    assert result["action"] == "UNKNOWN"


def test_json_with_surrounding_text():
    raw = (
        "Sure, here is the extracted intent:\n"
        '{"action": "approve_leave", "params": {"request_id": 5}, "cannot_do_reason": null}\n'
        "Let me know if you need anything else."
    )
    result = _parse_llm_json(raw)
    assert result["action"] == "approve_leave"
    assert result["params"]["request_id"] == 5


def test_json_with_reasoning_preamble():
    raw = (
        "Thinking: The user wants to apply for leave.\n"
        "Draft 1: apply_leave action.\n\n"
        '{"action": "apply_leave", "params": {"leave_type": "SICK", '
        '"start_date": "2026-05-10", "end_date": "2026-05-12", '
        '"reason": null, "is_half_day": false, "half_day_period": null}, '
        '"cannot_do_reason": null}'
    )
    result = _parse_llm_json(raw)
    assert result["action"] == "apply_leave"
    assert result["params"]["leave_type"] == "SICK"


def test_cannot_do_reason_returned():
    raw = '{"action": "approve_leave", "params": {}, "cannot_do_reason": "Not a manager"}'
    result = _parse_llm_json(raw)
    assert result["cannot_do_reason"] == "Not a manager"


def test_truncated_json_raises():
    raw = '{"action": "apply_leave", "params": {"leave_type": "SICK", "start_date":'
    with pytest.raises((json.JSONDecodeError, ValueError)):
        _parse_llm_json(raw)


def test_empty_string_raises():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        _parse_llm_json("")


def test_nested_params_preserved():
    raw = json.dumps({
        "action": "assign_employee_to_project",
        "params": {"employee_id": 4, "project_id": 1, "role": "AI Engineer"},
        "cannot_do_reason": None,
    })
    result = _parse_llm_json(raw)
    assert result["params"]["role"] == "AI Engineer"
    assert result["params"]["employee_id"] == 4
