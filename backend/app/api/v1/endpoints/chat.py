import json
import time
from typing import Generator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.employee import Employee, EmployeeRole
from app.models.ai_audit_log import AIIntent, ActionStatus
from app.schemas.chat import ChatRequest
from app.schemas.common import APIResponse
from app.services.ai.action_agent import run_action
from app.services.ai.audit import log_ai_interaction
from app.services.ai.hr_data_rag import query_hr_data
from app.services.ai.policy_rag import answer_policy_question, ingest_policies
from app.services.ai.pipeline import get_pipeline
from app.services.ai.router_agent import route_and_answer, classify_intent
from app.services.ai.sql_agent import run_sql_query

router = APIRouter()

_INTENT_MAP = {
    "POLICY_QA": AIIntent.POLICY_QA,
    "SQL_QUERY": AIIntent.SQL_QUERY,
    "HR_ACTION": AIIntent.HR_ACTION,
}


def _log_blocked(db: Session, user: Employee, message: str, blocked, t0: float) -> None:
    log_ai_interaction(
        db, user, message, AIIntent.UNKNOWN, ActionStatus.REFUSED,
        tool_name=blocked.route, latency_ms=(time.perf_counter() - t0) * 1000,
    )


@router.post("/policy", response_model=APIResponse)
def chat_policy(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t0 = time.perf_counter()
    try:
        message, blocked = get_pipeline().preprocess(payload.message, current_user)
        if blocked:
            _log_blocked(db, current_user, payload.message, blocked, t0)
            return APIResponse.ok({"answer": blocked.response, "sources": []})
        result = answer_policy_question(db, message, user_role=current_user.role, policy_group=current_user.policy_group, history=[h.dict() for h in payload.history], session_id=payload.session_id, user_id=current_user.id)
        log_ai_interaction(
            db, current_user, payload.message,
            intent=AIIntent.POLICY_QA,
            action_status=ActionStatus.SUCCESS if result["sources"] else ActionStatus.REFUSED,
            tool_name="policy_rag",
            records_accessed=[s["title"] for s in result["sources"]],
            latency_ms=(time.perf_counter()-t0)*1000,
        )
        return APIResponse.ok(result)
    except Exception as e:
        log_ai_interaction(db, current_user, payload.message, AIIntent.POLICY_QA, ActionStatus.ERROR, latency_ms=(time.perf_counter()-t0)*1000)
        return APIResponse.fail(str(e))


@router.post("/sql", response_model=APIResponse)
def chat_sql(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t0 = time.perf_counter()
    try:
        message, blocked = get_pipeline().preprocess(payload.message, current_user)
        if blocked:
            _log_blocked(db, current_user, payload.message, blocked, t0)
            return APIResponse.ok({"answer": blocked.response, "sql": "", "rows": [], "row_count": 0})
        result = run_sql_query(db, current_user, message, history=[h.dict() for h in payload.history], session_id=payload.session_id)
        status = ActionStatus.SUCCESS if result["rows"] else ActionStatus.REFUSED
        log_ai_interaction(
            db, current_user, payload.message,
            intent=AIIntent.SQL_QUERY,
            action_status=status,
            tool_name="sql_agent",
            records_accessed=[result["sql"]] if result["sql"] else None,
            latency_ms=(time.perf_counter()-t0)*1000,
        )
        return APIResponse.ok(result)
    except Exception as e:
        log_ai_interaction(db, current_user, payload.message, AIIntent.SQL_QUERY, ActionStatus.ERROR, latency_ms=(time.perf_counter()-t0)*1000)
        return APIResponse.fail(str(e))


@router.post("/actions", response_model=APIResponse)
def chat_actions(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t0 = time.perf_counter()
    try:
        message, blocked = get_pipeline().preprocess(payload.message, current_user)
        if blocked:
            _log_blocked(db, current_user, payload.message, blocked, t0)
            return APIResponse.ok({"answer": blocked.response, "success": False, "action": blocked.route, "data": None})
        result = run_action(db, current_user, message, history=[h.dict() for h in payload.history], session_id=payload.session_id, confirmed=payload.confirmed)
        log_ai_interaction(
            db, current_user, payload.message,
            intent=AIIntent.HR_ACTION,
            action_status=ActionStatus.SUCCESS if result["success"] else ActionStatus.REFUSED,
            tool_name=result["action"],
            records_accessed=[str(result["data"])] if result.get("data") else None,
            latency_ms=(time.perf_counter()-t0)*1000,
        )
        return APIResponse.ok(result)
    except Exception as e:
        log_ai_interaction(db, current_user, payload.message, AIIntent.HR_ACTION, ActionStatus.ERROR, latency_ms=(time.perf_counter()-t0)*1000)
        return APIResponse.fail(str(e))


@router.post("/router", response_model=APIResponse)
def chat_router(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t0 = time.perf_counter()
    try:
        result = get_pipeline().run(db, current_user, payload.message, history=[h.dict() for h in payload.history], session_id=payload.session_id)
        route_intent = result["route"]["intent"]
        action_status = ActionStatus.REFUSED if route_intent == "BLOCKED" else ActionStatus.SUCCESS
        log_ai_interaction(
            db, current_user, payload.message,
            intent=_INTENT_MAP.get(route_intent, AIIntent.UNKNOWN),
            action_status=action_status,
            tool_name=result.get("guardrail") or "router",
            latency_ms=(time.perf_counter()-t0)*1000,
        )
        return APIResponse.ok(result)
    except Exception as e:
        log_ai_interaction(db, current_user, payload.message, AIIntent.ROUTER, ActionStatus.ERROR, latency_ms=(time.perf_counter()-t0)*1000)
        return APIResponse.fail(str(e))


@router.post("/hr-data", response_model=APIResponse)
def chat_hr_data(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Query employee HR data. Restricted to MANAGER and ADMIN roles."""
    t0 = time.perf_counter()
    try:
        message, blocked = get_pipeline().preprocess(payload.message, current_user)
        if blocked:
            _log_blocked(db, current_user, payload.message, blocked, t0)
            return APIResponse.ok({"answer": blocked.response, "rows_found": 0, "rows": []})
        result = query_hr_data(
            message,
            current_user.role,
            employee_code=current_user.employee_code,
            employee_name=current_user.name,
            history=[h.dict() for h in payload.history],
            db=db,
            user_id=current_user.id,
            session_id=payload.session_id,
        )
        log_ai_interaction(
            db, current_user, message,
            intent=AIIntent.SQL_QUERY,
            action_status=ActionStatus.SUCCESS if result["rows_found"] else ActionStatus.REFUSED,
            tool_name="hr_data_rag",
            latency_ms=(time.perf_counter()-t0)*1000,
        )
        return APIResponse.ok(result)
    except Exception as e:
        log_ai_interaction(db, current_user, payload.message, AIIntent.SQL_QUERY, ActionStatus.ERROR, latency_ms=(time.perf_counter()-t0)*1000)
        return APIResponse.fail(str(e))


@router.post("/policy/ingest", response_model=APIResponse)
def ingest_policy_docs(
    current_user: Employee = Depends(require_role(EmployeeRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Admin-only: re-embed all active HR policies into the vector store."""
    count = ingest_policies(db)
    return APIResponse.ok({"chunks_ingested": count})


# ─── LangGraph endpoint ───────────────────────────────────────────────────────

@router.post("/langgraph", response_model=APIResponse)
def chat_langgraph(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """LangGraph multi-agent orchestration — passes through guardrail pipeline then routes via graph."""
    t0 = time.perf_counter()
    try:
        message, blocked = get_pipeline().preprocess(payload.message, current_user)
        if blocked:
            _log_blocked(db, current_user, payload.message, blocked, t0)
            return APIResponse.ok({"route": {"intent": "BLOCKED"}, "result": {"answer": blocked.response}, "guardrail": blocked.route})
        from app.services.ai.langgraph_agent import run_langgraph
        result = run_langgraph(db, current_user, message, history=[h.dict() for h in payload.history], session_id=payload.session_id)
        route_intent = result["route"]["intent"]
        log_ai_interaction(
            db, current_user, payload.message,
            intent=_INTENT_MAP.get(route_intent, AIIntent.UNKNOWN),
            action_status=ActionStatus.SUCCESS,
            tool_name="langgraph",
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
        return APIResponse.ok(result)
    except Exception as e:
        log_ai_interaction(db, current_user, payload.message, AIIntent.ROUTER, ActionStatus.ERROR,
                           latency_ms=(time.perf_counter() - t0) * 1000)
        return APIResponse.fail(str(e))


# ─── Streamable HTTP (NDJSON) endpoint ───────────────────────────────────────

def _ndjson(event_type: str, data: dict) -> str:
    return json.dumps({"type": event_type, **data}) + "\n"


def _stream_router(
    db: Session, user: Employee, message: str, history: list = None, session_id: str = None,
) -> Generator[str, None, None]:
    yield _ndjson("status", {"message": "Checking guardrails…"})

    processed, blocked = get_pipeline().preprocess(message, user)
    if blocked:
        yield _ndjson("result", {
            "route": {"intent": "BLOCKED", "confidence": 1.0, "reason": f"Guardrail: {blocked.route}", "router": "guardrail"},
            "result": {"answer": blocked.response},
            "guardrail": blocked.route,
        })
        yield _ndjson("done", {})
        return

    yield _ndjson("status", {"message": "Classifying intent…"})

    route = classify_intent(processed, history=history, db=db, user_id=user.id, session_id=session_id)
    intent = route["intent"]
    yield _ndjson("status", {"message": f"Intent: {intent} — {route['reason']}"})

    try:
        if intent == "POLICY_QA":
            yield _ndjson("status", {"message": "Searching HR policies…"})
            from app.services.ai.policy_rag import answer_policy_question
            result = answer_policy_question(db, processed, user_role=user.role, policy_group=user.policy_group, history=history, session_id=session_id, user_id=user.id)
            yield _ndjson("result", {"route": route, "result": dict(result)})

        elif intent == "SQL_QUERY":
            yield _ndjson("status", {"message": "Generating SQL query…"})
            result = run_sql_query(db, user, processed, history=history, session_id=session_id)
            yield _ndjson("result", {"route": route, "result": dict(result)})

        elif intent == "HR_ACTION":
            yield _ndjson("status", {"message": "Processing HR action…"})
            result = run_action(db, user, processed, history=history, session_id=session_id)
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
        _stream_router(db, current_user, payload.message, history=[h.dict() for h in payload.history], session_id=payload.session_id),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
