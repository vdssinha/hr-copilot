"""
Unified AI router — classifies user intent and dispatches to the correct sub-system.

Routing strategy is controlled by AI_ROUTER_TYPE in config:
  "semantic" — embedding cosine similarity only (fast, zero LLM cost)
  "llm"      — original LLM classifier (context-aware, costs tokens)
  "hybrid"   — semantic first; LLM fallback when score < AI_SEMANTIC_ROUTER_THRESHOLD
"""
import json
import re
from functools import lru_cache
from typing import Literal, TypedDict

from sqlalchemy.orm import Session

from app.core.config import (
    AI_MAX_TOKENS_SMART_COPILOT_INTENT,
    AI_ROUTER_TYPE,
    AI_SEMANTIC_ROUTER_THRESHOLD,
)
from app.models.employee import Employee
from app.services.ai import factory as _factory
from app.services.ai.core.memory.context import build_history_block
from app.services.ai.core.memory.memory import build_memory_section, maybe_summarize

Intent = Literal["POLICY_QA", "SQL_QUERY", "HR_ACTION", "UNKNOWN"]

_CLASSIFY_SYSTEM = """You are an HR query intent classifier.

Your job is to map each user message to the correct intent so the right subsystem handles it.
You MUST NOT answer the question — classify only.

----------------------
CORE BEHAVIOR
----------------------

1. Understand Intent
   - Read the full message and prior conversation to determine what the user actually wants.
   - A short or ambiguous reply ("sick", "yes", "two days") continues the intent of the last turn.

2. Context Resolution
   - Use conversation history and memory to resolve pronouns, implicit references, and follow-ups.
   - A clarification answer belongs to the same intent as the question it answers.

3. Intent Categories
   - POLICY_QA  — user wants to know a rule, entitlement, procedure, or company policy
   - SQL_QUERY  — user wants facts from structured data: headcount, records, assignments, projects
   - HR_ACTION  — user wants something done: apply leave, create ticket, approve request, assign task
   - UNKNOWN    — cannot be confidently mapped to any of the above

4. Confidence
   - Reflect genuine uncertainty. Use lower confidence when context is thin or the message is ambiguous.

----------------------
DECISION RULE
----------------------

- Clear intent → classify with high confidence
- Ambiguous but inferable from history → classify with moderate confidence
- Cannot determine → UNKNOWN

Respond ONLY with JSON: {{"intent": "<INTENT>", "confidence": 0.0-1.0, "reason": "<one sentence>"}}

{memory_section}"""


class RouteResult(TypedDict):
    intent: Intent
    confidence: float
    reason: str
    router: str  # "semantic" | "llm" — which path produced this result


@lru_cache(maxsize=1)
def _get_semantic_router():
    """Build once, reuse across requests. lru_cache makes it a lazy singleton."""
    from app.services.ai.routing.intent_routes import ALL_ROUTES
    from app.services.ai.routing.semantic_router import SemanticRouter

    encoder = _factory.get_embedder()
    return SemanticRouter(
        encoder=encoder,
        routes=ALL_ROUTES,
        threshold=AI_SEMANTIC_ROUTER_THRESHOLD,
    )


def _classify_via_semantic(message: str) -> RouteResult:
    sr = _get_semantic_router()
    name, score = sr(message)
    intent: Intent = name if name in ("POLICY_QA", "SQL_QUERY", "HR_ACTION") else "UNKNOWN"
    return RouteResult(
        intent=intent,
        confidence=round(score, 4),
        reason=f"Semantic match (cosine={score:.3f})",
        router="semantic",
    )


def _classify_via_llm(
    message: str,
    history: list = None,
    db=None,
    user_id: int = None,
    session_id: str = None,
) -> RouteResult:
    llm = _factory.get_llm_provider()
    history_block = build_history_block(history or [])
    prompt = f"{history_block} {message}" if history_block else message

    mem = build_memory_section(db, user_id, session_id, "router") if db and user_id else ""
    system = _CLASSIFY_SYSTEM.format(memory_section=mem)

    raw = llm.generate(prompt, system=system, max_tokens=AI_MAX_TOKENS_SMART_COPILOT_INTENT)
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
            router="llm",
        )
    except (json.JSONDecodeError, ValueError):
        m = re.search(r'"intent"\s*:\s*"(POLICY_QA|SQL_QUERY|HR_ACTION|UNKNOWN)"', raw)
        if m:
            return RouteResult(intent=m.group(1), confidence=0.5, reason="Parsed from truncated response.", router="llm")
        return RouteResult(intent="UNKNOWN", confidence=0.0, reason="Could not parse intent.", router="llm")


def classify_intent(
    message: str,
    history: list = None,
    db=None,
    user_id: int = None,
    session_id: str = None,
) -> RouteResult:
    if AI_ROUTER_TYPE == "semantic":
        return _classify_via_semantic(message)

    if AI_ROUTER_TYPE == "llm":
        return _classify_via_llm(message, history, db, user_id, session_id)

    # hybrid: semantic first, LLM fallback on low confidence
    result = _classify_via_semantic(message)
    if result["confidence"] >= AI_SEMANTIC_ROUTER_THRESHOLD and result["intent"] != "UNKNOWN":
        return result
    return _classify_via_llm(message, history, db, user_id, session_id)


def route_and_answer(db: Session, user: Employee, message: str, history: list = None, session_id: str = None) -> dict:
    """Classify intent then dispatch to the appropriate agent."""
    maybe_summarize(db, user.id, session_id, "router", history or [])
    route = classify_intent(message, history=history, db=db, user_id=user.id, session_id=session_id)

    if route["intent"] == "POLICY_QA":
        from app.services.ai.agents.policy_rag import answer_policy_question
        result = answer_policy_question(db, message, user_role=user.role, policy_group=user.policy_group, history=history, session_id=session_id, user_id=user.id)
        return {"route": route, "result": result}

    if route["intent"] == "SQL_QUERY":
        from app.services.ai.agents.sql_agent import run_sql_query
        result = run_sql_query(db, user, message, history=history, session_id=session_id)
        return {"route": route, "result": result}

    if route["intent"] == "HR_ACTION":
        from app.services.ai.agents.action_agent import run_action
        result = run_action(db, user, message, history=history, session_id=session_id)
        return {"route": route, "result": result}

    return {
        "route": route,
        "result": {
            "answer": "I'm not sure how to help with that. Try asking about HR policies, employee data, or HR tasks.",
        },
    }
