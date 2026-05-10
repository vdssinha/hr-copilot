"""
LangGraph multi-agent orchestration for the HR Copilot.

Graph flow:
  START → classify_intent → (conditional route) →
    policy_rag  → END
    sql_agent   → END
    action_agent → END
    unknown     → END

Each node receives the full AgentState, mutates result/error, and returns.
db and user are injected at graph invocation time via state initialisation.
"""
from typing import Optional, Any
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.services.ai.router_agent import classify_intent


class AgentState(TypedDict):
    # inputs — set once before graph.invoke()
    message: str
    db: Any          # sqlalchemy Session (not serialised)
    user: Any        # Employee ORM object (not serialised)
    history: list    # prior conversation turns for context resolution

    # mutable across nodes
    intent: str
    confidence: float
    reason: str
    result: Optional[dict]
    error: Optional[str]


# ─── Nodes ───────────────────────────────────────────────────────────────────

def node_classify(state: AgentState) -> dict:
    route = classify_intent(state["message"], history=state.get("history", []))
    return {
        "intent": route["intent"],
        "confidence": route["confidence"],
        "reason": route["reason"],
    }


def node_policy_rag(state: AgentState) -> dict:
    from app.services.ai.policy_rag import answer_policy_question
    user = state["user"]
    try:
        result = answer_policy_question(
            state["db"], state["message"],
            user_role=user.role,
            policy_group=user.policy_group,
            history=state.get("history", []),
        )
        return {"result": dict(result)}
    except Exception as e:
        return {"error": str(e), "result": {"answer": "Policy lookup failed.", "sources": []}}


def node_sql_agent(state: AgentState) -> dict:
    from app.services.ai.sql_agent import run_sql_query
    try:
        result = run_sql_query(state["db"], state["user"], state["message"], history=state.get("history", []))
        return {"result": dict(result)}
    except Exception as e:
        return {"error": str(e), "result": {"answer": "Data query failed.", "sql": "", "rows": [], "row_count": 0}}


def node_action_agent(state: AgentState) -> dict:
    from app.services.ai.action_agent import run_action
    try:
        result = run_action(state["db"], state["user"], state["message"], history=state.get("history", []))
        return {"result": dict(result)}
    except Exception as e:
        return {"error": str(e), "result": {"answer": "Action failed.", "action": "UNKNOWN", "success": False, "data": None}}


def node_unknown(state: AgentState) -> dict:
    return {
        "result": {
            "answer": "I'm not sure how to help with that. Try asking about HR policies, employee data, or HR tasks.",
        }
    }


# ─── Routing ─────────────────────────────────────────────────────────────────

def _route(state: AgentState) -> str:
    intent = state.get("intent", "UNKNOWN")
    mapping = {
        "POLICY_QA": "policy_rag",
        "SQL_QUERY": "sql_agent",
        "HR_ACTION": "action_agent",
    }
    return mapping.get(intent, "unknown")


# ─── Graph construction ───────────────────────────────────────────────────────

def build_hr_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("classify", node_classify)
    graph.add_node("policy_rag", node_policy_rag)
    graph.add_node("sql_agent", node_sql_agent)
    graph.add_node("action_agent", node_action_agent)
    graph.add_node("unknown", node_unknown)

    graph.set_entry_point("classify")

    graph.add_conditional_edges(
        "classify",
        _route,
        {
            "policy_rag": "policy_rag",
            "sql_agent": "sql_agent",
            "action_agent": "action_agent",
            "unknown": "unknown",
        },
    )

    graph.add_edge("policy_rag", END)
    graph.add_edge("sql_agent", END)
    graph.add_edge("action_agent", END)
    graph.add_edge("unknown", END)

    return graph.compile()


# Singleton compiled graph — built once at import time.
_hr_graph = build_hr_graph()


def run_langgraph(db: Session, user: Employee, message: str, history: list = None) -> dict:
    """Run the HR copilot LangGraph and return a unified result dict."""
    initial_state: AgentState = {
        "message": message,
        "db": db,
        "user": user,
        "history": history or [],
        "intent": "",
        "confidence": 0.0,
        "reason": "",
        "result": None,
        "error": None,
    }
    final_state = _hr_graph.invoke(initial_state)
    return {
        "route": {
            "intent": final_state["intent"],
            "confidence": final_state["confidence"],
            "reason": final_state["reason"],
        },
        "result": final_state.get("result") or {},
        "error": final_state.get("error"),
    }
