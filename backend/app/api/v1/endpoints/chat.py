import json
from typing import Generator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.employee import Employee
from app.models.ai_audit_log import AIIntent, ActionStatus
from app.schemas.chat import ChatRequest
from app.schemas.common import APIResponse
from app.services.ai.action_agent import run_action
from app.services.ai.audit import log_ai_interaction
from app.services.ai.policy_rag import answer_policy_question, ingest_policies
from app.services.ai.router_agent import route_and_answer, classify_intent
from app.services.ai.sql_agent import run_sql_query

router = APIRouter()


@router.post("/policy", response_model=APIResponse)
def chat_policy(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = answer_policy_question(db, payload.message, user_role=current_user.role)
        log_ai_interaction(
            db, current_user, payload.message,
            intent=AIIntent.POLICY_QA,
            action_status=ActionStatus.SUCCESS if result["sources"] else ActionStatus.REFUSED,
            tool_name="policy_rag",
            records_accessed=[s["title"] for s in result["sources"]],
        )
        return APIResponse.ok(result)
    except Exception as e:
        log_ai_interaction(db, current_user, payload.message, AIIntent.POLICY_QA, ActionStatus.ERROR)
        return APIResponse.fail(str(e))


@router.post("/sql", response_model=APIResponse)
def chat_sql(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = run_sql_query(db, current_user, payload.message)
        status = ActionStatus.SUCCESS if result["rows"] else ActionStatus.REFUSED
        log_ai_interaction(
            db, current_user, payload.message,
            intent=AIIntent.SQL_QUERY,
            action_status=status,
            tool_name="sql_agent",
            records_accessed=[result["sql"]] if result["sql"] else None,
        )
        return APIResponse.ok(result)
    except Exception as e:
        log_ai_interaction(db, current_user, payload.message, AIIntent.SQL_QUERY, ActionStatus.ERROR)
        return APIResponse.fail(str(e))


@router.post("/actions", response_model=APIResponse)
def chat_actions(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = run_action(db, current_user, payload.message)
        log_ai_interaction(
            db, current_user, payload.message,
            intent=AIIntent.HR_ACTION,
            action_status=ActionStatus.SUCCESS if result["success"] else ActionStatus.REFUSED,
            tool_name=result["action"],
            records_accessed=[str(result["data"])] if result.get("data") else None,
        )
        return APIResponse.ok(result)
    except Exception as e:
        log_ai_interaction(db, current_user, payload.message, AIIntent.HR_ACTION, ActionStatus.ERROR)
        return APIResponse.fail(str(e))


@router.post("/router", response_model=APIResponse)
def chat_router(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = route_and_answer(db, current_user, payload.message)
        route_intent = result["route"]["intent"]
        intent_map = {
            "POLICY_QA": AIIntent.POLICY_QA,
            "SQL_QUERY": AIIntent.SQL_QUERY,
            "HR_ACTION": AIIntent.HR_ACTION,
        }
        log_ai_interaction(
            db, current_user, payload.message,
            intent=intent_map.get(route_intent, AIIntent.UNKNOWN),
            action_status=ActionStatus.SUCCESS,
            tool_name="router",
        )
        return APIResponse.ok(result)
    except Exception as e:
        log_ai_interaction(db, current_user, payload.message, AIIntent.ROUTER, ActionStatus.ERROR)
        return APIResponse.fail(str(e))


@router.post("/policy/ingest", response_model=APIResponse)
def ingest_policy_docs(
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: re-embed all active HR policies into the vector store."""
    from app.models.employee import EmployeeRole
    if current_user.role != EmployeeRole.ADMIN:
        return APIResponse.fail("Only admins can trigger policy ingestion.")
    count = ingest_policies(db)
    return APIResponse.ok({"chunks_ingested": count})


# ─── LangGraph endpoint ───────────────────────────────────────────────────────

@router.post("/langgraph", response_model=APIResponse)
def chat_langgraph(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """LangGraph multi-agent orchestration — identical behaviour to /router but via graph."""
    try:
        from app.services.ai.langgraph_agent import run_langgraph
        result = run_langgraph(db, current_user, payload.message)
        route_intent = result["route"]["intent"]
        intent_map = {
            "POLICY_QA": AIIntent.POLICY_QA,
            "SQL_QUERY": AIIntent.SQL_QUERY,
            "HR_ACTION": AIIntent.HR_ACTION,
        }
        log_ai_interaction(
            db, current_user, payload.message,
            intent=intent_map.get(route_intent, AIIntent.UNKNOWN),
            action_status=ActionStatus.SUCCESS,
            tool_name="langgraph",
        )
        return APIResponse.ok(result)
    except Exception as e:
        log_ai_interaction(db, current_user, payload.message, AIIntent.ROUTER, ActionStatus.ERROR)
        return APIResponse.fail(str(e))


# ─── Streamable HTTP (NDJSON) endpoint ───────────────────────────────────────

def _ndjson(event_type: str, data: dict) -> str:
    return json.dumps({"type": event_type, **data}) + "\n"


def _stream_router(
    db: Session, user: Employee, message: str
) -> Generator[str, None, None]:
    yield _ndjson("status", {"message": "Classifying intent…"})

    route = classify_intent(message)
    intent = route["intent"]
    yield _ndjson("status", {"message": f"Intent: {intent} — {route['reason']}"})

    try:
        if intent == "POLICY_QA":
            yield _ndjson("status", {"message": "Searching HR policies…"})
            from app.services.ai.policy_rag import answer_policy_question
            result = answer_policy_question(db, message, user_role=user.role)
            yield _ndjson("result", {"route": route, "result": dict(result)})

        elif intent == "SQL_QUERY":
            yield _ndjson("status", {"message": "Generating SQL query…"})
            result = run_sql_query(db, user, message)
            yield _ndjson("result", {"route": route, "result": dict(result)})

        elif intent == "HR_ACTION":
            yield _ndjson("status", {"message": "Processing HR action…"})
            result = run_action(db, user, message)
            yield _ndjson("result", {"route": route, "result": dict(result)})

        else:
            yield _ndjson("result", {
                "route": route,
                "result": {"answer": "I'm not sure how to help with that. Try asking about HR policies, employee data, or HR tasks."},
            })
    except Exception as e:
        yield _ndjson("error", {"message": str(e)})

    yield _ndjson("done", {})


@router.post("/router/stream")
def chat_router_stream(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Streamable HTTP (NDJSON) version of /router — emits status events then the final result."""
    return StreamingResponse(
        _stream_router(db, current_user, payload.message),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
