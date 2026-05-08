from fastapi import APIRouter, Depends
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
from app.services.ai.router_agent import route_and_answer
from app.services.ai.sql_agent import run_sql_query

router = APIRouter()


@router.post("/policy", response_model=APIResponse)
def chat_policy(
    payload: ChatRequest,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = answer_policy_question(db, payload.message)
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
