import json
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.ai_audit_log import AIAuditLog, AIIntent, ActionStatus
from app.models.employee import Employee


def log_ai_interaction(
    db: Session,
    user: Employee,
    message: str,
    intent: AIIntent,
    action_status: ActionStatus,
    tool_name: Optional[str] = None,
    records_accessed: Optional[List] = None,
) -> None:
    entry = AIAuditLog(
        user_id=user.id,
        role=user.role.value,
        message=message,
        intent=intent,
        tool_name=tool_name,
        action_status=action_status,
        records_accessed=json.dumps(records_accessed) if records_accessed else None,
    )
    db.add(entry)
    db.commit()
