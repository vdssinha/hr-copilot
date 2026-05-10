"""
HR Task Automation Agent.
Extracts intent + params from user message, checks permissions,
then dispatches to the appropriate backend API tool.
"""
import json
import re
from datetime import date as _date
from typing import Optional, TypedDict

from sqlalchemy.orm import Session

from app.core.config import AI_MAX_TOKENS_ACTION_AGENT_EXTRACT, AI_MAX_TOKENS_ACTION_AGENT_SUMMARY
from app.services.ai.context import build_history_block
from app.models.employee import Employee
from app.services.ai.api_tools import (
    apply_leave, check_leave_balance,
    approve_leave, reject_leave,
    create_ticket, assign_ticket,
    create_announcement, assign_employee_to_project,
)
from app.services.ai import factory as _factory
from app.services.ai.permissions import can_perform, allowed_actions

_EXTRACT_SYSTEM = """You are an HR task intent extractor. Given a user message (plus prior conversation and today's date in the prompt), extract the intended action and its parameters as JSON.

Respond ONLY with a JSON object in this exact format:
{
  "action": "<action_name | UNKNOWN | CLARIFY>",
  "params": { ... },
  "cannot_do_reason": "<if action not in allowed_actions, explain why; else null>",
  "clarification_question": "<friendly question when truly required params are missing; else null>"
}

Available actions and their parameters:
- apply_leave: leave_type (CASUAL/SICK/ANNUAL/UNPAID), start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), reason (str, optional), is_half_day (bool), half_day_period (MORNING/AFTERNOON/null)
- check_leave_balance: year (optional int)
- approve_leave: request_id (int)
- reject_leave: request_id (int)
- create_ticket: title (str), description (str), category (IT/HR/FACILITIES/FINANCE/OTHER), priority (LOW/MEDIUM/HIGH/CRITICAL)
- assign_ticket: ticket_id (int), assignee_id (int), status (optional)
- create_announcement: title (str), content (str), category (GENERAL/HR/IT/FACILITIES/CULTURE), is_pinned (bool)
- assign_employee_to_project: employee_id (int), project_id (int), role (str)

SMART DEFAULTS — infer these without asking:
- is_half_day: default false unless user says "half day", "morning", or "afternoon"
- half_day_period: null unless user specifies morning/afternoon
- reason: use "" (empty string) if not provided — do NOT ask for it
- priority for tickets: default "MEDIUM" unless user specifies urgency
- is_pinned for announcements: default false unless user says "pin" or "important"
- leave_type: infer from context when obvious — "sick", "fever", "ill", "unwell" → SICK; "vacation", "holiday", "trip" → ANNUAL; "personal", "casual" → CASUAL

DATE RESOLUTION — Today's date is provided below as "Today's date: YYYY-MM-DD".
Convert relative dates using it:
- "today" → today
- "tomorrow" → today + 1 day
- "day after tomorrow" → today + 2 days
- "next Monday/Tuesday/..." → compute from today
- "X days from today" → compute
- "2 days" or "for 2 days" without explicit start → start = today, end = today + 1 day
Always output YYYY-MM-DD.

CONTEXT ACCUMULATION — Prior conversation is included. Parameters already provided in earlier turns are still valid. Collect all params across turns before deciding to CLARIFY.

CLARIFY only if:
- action is identified AND a truly required param (leave_type, start_date, end_date, ticket title, or similar) CANNOT be inferred from the full conversation so far
- Ask for ALL missing required params in ONE question — never ask one at a time

If the message doesn't match any action, use action: "UNKNOWN"."""


class ActionResult(TypedDict):
    answer: str
    action: str
    success: bool
    data: Optional[dict]


def _parse_llm_json(raw: str) -> dict:
    raw = raw.strip()
    # Strip markdown fences
    raw = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip("` \n")
    # If there's still extra text, extract the first {...} block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)
    return json.loads(raw)


def _build_extract_prompt(message: str, user: Employee, history: list = None) -> str:
    today = _date.today().isoformat()
    actions = sorted(allowed_actions(user))
    history_block = build_history_block(history or [])
    preamble = f"{history_block}\n" if history_block else ""
    return (
        f"{preamble}"
        f"Today's date: {today}\n"
        f"User role: {user.role.value}\n"
        f"Allowed actions for this user: {actions}\n\n"
        f"User message: {message}"
    )


def _summarize_result(llm, action: str, message: str, result: dict) -> str:
    if not result.get("success"):
        return result.get("error", "The action could not be completed.")
    data = result.get("data", {})
    prompt = (
        f"The user asked: {message}\n"
        f"Action executed: {action}\n"
        f"Result: {json.dumps(data)}\n\n"
        "Write a clear, friendly 1-2 sentence confirmation of what was done. "
        "Do not mention JSON, IDs, or technical details unless directly relevant."
    )
    return llm.generate(prompt, system="Summarize HR action results clearly.", max_tokens=AI_MAX_TOKENS_ACTION_AGENT_SUMMARY)


def run_action(db: Session, user: Employee, message: str, history: list = None) -> ActionResult:
    llm = _factory.get_llm_provider()

    # Step 1: Extract intent + params
    prompt = _build_extract_prompt(message, user, history=history)
    raw = llm.generate(prompt, system=_EXTRACT_SYSTEM, max_tokens=AI_MAX_TOKENS_ACTION_AGENT_EXTRACT)

    try:
        parsed = _parse_llm_json(raw)
    except (json.JSONDecodeError, ValueError):
        return ActionResult(
            answer="I couldn't understand the action. Please rephrase your request.",
            action="UNKNOWN", success=False, data=None,
        )

    action = parsed.get("action", "UNKNOWN")
    params = parsed.get("params", {})
    cannot_do = parsed.get("cannot_do_reason")
    clarification_question = parsed.get("clarification_question")

    # Step 2: Clarification needed — missing required params
    if action == "CLARIFY":
        question = clarification_question or "Could you provide more details? (e.g. leave type, dates)"
        return ActionResult(answer=question, action="CLARIFY", success=False, data=None)

    # Step 3: Permission check
    if action == "UNKNOWN":
        return ActionResult(
            answer="I'm not sure what action you'd like to perform. Could you be more specific?",
            action="UNKNOWN", success=False, data=None,
        )

    if cannot_do:
        return ActionResult(
            answer=f"You do not have permission to {action.replace('_', ' ')}.",
            action=action, success=False, data=None,
        )

    if not can_perform(user, action):
        return ActionResult(
            answer=f"You do not have permission to {action.replace('_', ' ')}.",
            action=action, success=False, data=None,
        )

    # Step 3: Dispatch to tool
    dispatch = {
        "apply_leave": lambda: apply_leave(db, user, **params),
        "check_leave_balance": lambda: check_leave_balance(db, user, **params),
        "approve_leave": lambda: approve_leave(db, user, **params),
        "reject_leave": lambda: reject_leave(db, user, **params),
        "create_ticket": lambda: create_ticket(db, user, **params),
        "assign_ticket": lambda: assign_ticket(db, user, **params),
        "create_announcement": lambda: create_announcement(db, user, **params),
        "assign_employee_to_project": lambda: assign_employee_to_project(db, user, **params),
    }

    handler = dispatch.get(action)
    if not handler:
        return ActionResult(
            answer="That action is not yet supported.", action=action, success=False, data=None
        )

    try:
        result = handler()
    except TypeError as e:
        return ActionResult(
            answer=f"Missing required information for {action.replace('_', ' ')}: {e}",
            action=action, success=False, data=None,
        )

    # Step 4: Summarize
    answer = _summarize_result(llm, action, message, result)
    return ActionResult(
        answer=answer,
        action=action,
        success=result.get("success", False),
        data=result.get("data"),
    )
