"""
Unified AI router — classifies user intent and dispatches to the correct sub-system.
"""
import json
import re
from typing import Literal, TypedDict

from sqlalchemy.orm import Session

from app.core.config import AI_MAX_TOKENS_SMART_COPILOT_INTENT
from app.models.employee import Employee
from app.services.ai import factory as _factory

Intent = Literal["POLICY_QA", "SQL_QUERY", "HR_ACTION", "UNKNOWN"]

_CLASSIFY_SYSTEM = """You are an HR query intent classifier.
Given a user message, classify it into exactly one of these intents:
- POLICY_QA: questions about HR policies, rules, benefits, attendance, leave entitlements
- SQL_QUERY: questions about employee data, projects, assignments, skills — requiring data lookup
- HR_ACTION: requests to perform an action (apply leave, create ticket, approve request, etc.)
- UNKNOWN: cannot be classified

Respond ONLY with JSON: {"intent": "<INTENT>", "confidence": 0.0-1.0, "reason": "<one sentence>"}"""


class RouteResult(TypedDict):
    intent: Intent
    confidence: float
    reason: str


def classify_intent(message: str) -> RouteResult:
    llm = _factory.get_llm_provider()
    raw = llm.generate(message, system=_CLASSIFY_SYSTEM, max_tokens=AI_MAX_TOKENS_SMART_COPILOT_INTENT)

    raw = raw.strip()
    raw = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip("` \n")

    try:
        parsed = json.loads(raw)
        intent = parsed.get("intent", "UNKNOWN")
        if intent not in ("POLICY_QA", "SQL_QUERY", "HR_ACTION", "UNKNOWN"):
            intent = "UNKNOWN"
        return RouteResult(
            intent=intent,
            confidence=float(parsed.get("confidence", 0.5)),
            reason=parsed.get("reason", ""),
        )
    except (json.JSONDecodeError, ValueError):
        # Truncated response (reasoning model used most of the token budget) —
        # extract intent via regex before giving up.
        m = re.search(r'"intent"\s*:\s*"(POLICY_QA|SQL_QUERY|HR_ACTION|UNKNOWN)"', raw)
        if m:
            return RouteResult(intent=m.group(1), confidence=0.5, reason="Parsed from truncated response.")
        return RouteResult(intent="UNKNOWN", confidence=0.0, reason="Could not parse intent.")


def route_and_answer(db: Session, user: Employee, message: str) -> dict:
    """Classify intent then dispatch to the appropriate agent."""
    route = classify_intent(message)

    if route["intent"] == "POLICY_QA":
        from app.services.ai.policy_rag import answer_policy_question
        result = answer_policy_question(db, message, user_role=user.role, policy_group=user.policy_group)
        return {"route": route, "result": result}

    if route["intent"] == "SQL_QUERY":
        from app.services.ai.sql_agent import run_sql_query
        result = run_sql_query(db, user, message)
        return {"route": route, "result": result}

    if route["intent"] == "HR_ACTION":
        from app.services.ai.action_agent import run_action
        result = run_action(db, user, message)
        return {"route": route, "result": result}

    return {
        "route": route,
        "result": {
            "answer": "I'm not sure how to help with that. Try asking about HR policies, employee data, or HR tasks.",
        },
    }
