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
from app.services.ai.memory import build_memory_section, maybe_summarize, store_agent_turn
from app.services.ai.api_tools import (
    apply_leave, check_leave_balance,
    approve_leave, reject_leave,
    list_pending_approvals, get_my_leaves,
    create_ticket, assign_ticket, check_ticket_status,
    create_announcement, assign_employee_to_project,
    view_own_projects, search_employees_by_skill,
    check_project_assignments, create_project,
)
from app.services.ai import factory as _factory
from app.services.ai.permissions import can_perform, allowed_actions

_EXTRACT_SYSTEM = """You are an HR task intent extractor.

Your job is to read the user's message, resolve intent from the full conversation, and return structured JSON for execution.
You MUST NOT execute anything yourself — output JSON only.

----------------------
CORE BEHAVIOR
----------------------

1. Understand Intent
   - Identify the intended action and extract all required parameters.
   - Use the full conversation history and today's date (provided in the prompt) to resolve context.

2. Smart Input Handling
   - Resolve relative dates ("today", "tomorrow", "next Monday") using the date provided in the prompt.
   - A duration without a start date (e.g., "for 2 days") implies start = today.
   - Infer leave type when the context makes it unambiguous (illness implies sick leave; vacation implies annual; casual personal errand implies casual).
   - Apply safe defaults rather than asking: is_half_day = false, half_day_period = null, reason = "", ticket priority = MEDIUM, announcement is_pinned = false.
   - DO NOT infer critical parameters (leave dates, ticket title) when genuinely absent from the entire conversation.

3. Context Accumulation
   - Parameters provided in earlier turns remain valid. Collect across turns before deciding CLARIFY.
   - A short reply ("sick", "yes", "two days") is a continuation — resolve it against the last question.

4. CLARIFY Discipline
   - Use CLARIFY only when a truly required parameter cannot be inferred from any turn.
   - Ask for ALL missing required parameters in ONE question — never ask one at a time.

5. Permission Awareness
   - The user's allowed actions are listed in the prompt. If the requested action is not permitted, name the action correctly and explain via cannot_do_reason.

----------------------
OUTPUT FORMAT
----------------------

Respond ONLY with JSON:
{{
  "action": "<action_name | UNKNOWN | CLARIFY>",
  "params": {{ ... }},
  "cannot_do_reason": "<explain if action not permitted; else null>",
  "clarification_question": "<single question covering ALL missing params; else null>"
}}

Available actions:
- apply_leave: leave_type (CASUAL/SICK/ANNUAL/UNPAID), start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), reason (str, optional), is_half_day (bool), half_day_period (MORNING/AFTERNOON/null)
- check_leave_balance: year (optional int)
- get_my_leaves: limit (optional int, default 20) — list own leave requests with status
- approve_leave: request_id (int)
- reject_leave: request_id (int)
- list_pending_approvals: no params — list pending leave requests for your direct reports
- create_ticket: title (str), description (str), category (IT/HR/FACILITIES/FINANCE/OTHER), priority (LOW/MEDIUM/HIGH/CRITICAL)
- check_ticket_status: limit (optional int, default 20) — list own tickets with their status
- assign_ticket: ticket_id (int), assignee_id (int), status (optional)
- create_announcement: title (str), content (str), category (GENERAL/HR/IT/FACILITIES/CULTURE), is_pinned (bool)
- assign_employee_to_project: employee_id (int), project_id (int), role (str)
- view_own_projects: no params — list own active project assignments
- search_employees_by_skill: skill_name (str) — find employees with a given skill
- check_project_assignments: no params — list project assignments for your team
- create_project: name (str), description (str, optional), status (PLANNING/ONGOING/COMPLETED/ON_HOLD, optional)

----------------------
DECISION RULE
----------------------

- All required params present or inferable → output action with full params
- Partial ambiguity resolvable from context → infer and proceed
- Truly missing critical param → CLARIFY with one combined question
- Action not in allowed list → name the action, explain in cannot_do_reason
- Message matches no action → UNKNOWN

{memory_section}"""


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


def run_action(db: Session, user: Employee, message: str, history: list = None, session_id: Optional[str] = None) -> ActionResult:
    maybe_summarize(db, user.id, session_id, "action_agent", history or [])
    mem = build_memory_section(db, user.id, session_id, "action_agent")
    extract_system = _EXTRACT_SYSTEM.format(memory_section=mem)

    llm = _factory.get_llm_provider()

    # Step 1: Extract intent + params
    prompt = _build_extract_prompt(message, user, history=history)
    raw = llm.generate(prompt, system=extract_system, max_tokens=AI_MAX_TOKENS_ACTION_AGENT_EXTRACT)

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
        "get_my_leaves": lambda: get_my_leaves(db, user, **params),
        "approve_leave": lambda: approve_leave(db, user, **params),
        "reject_leave": lambda: reject_leave(db, user, **params),
        "list_pending_approvals": lambda: list_pending_approvals(db, user),
        "create_ticket": lambda: create_ticket(db, user, **params),
        "check_ticket_status": lambda: check_ticket_status(db, user, **params),
        "assign_ticket": lambda: assign_ticket(db, user, **params),
        "create_announcement": lambda: create_announcement(db, user, **params),
        "assign_employee_to_project": lambda: assign_employee_to_project(db, user, **params),
        "view_own_projects": lambda: view_own_projects(db, user),
        "search_employees_by_skill": lambda: search_employees_by_skill(db, user, **params),
        "check_project_assignments": lambda: check_project_assignments(db, user),
        "create_project": lambda: create_project(db, user, **params),
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
    if session_id and result.get("success"):
        store_agent_turn(db, user.id, session_id, "action_agent", f"Executed {action}: {message[:100]}")
    return ActionResult(
        answer=answer,
        action=action,
        success=result.get("success", False),
        data=result.get("data"),
    )
