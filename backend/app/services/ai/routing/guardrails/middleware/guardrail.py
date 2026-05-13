"""
Semantic guardrail middleware.

Uses a SemanticRouter loaded with off_topic, jailbreak, and exfiltration routes
to detect and reject messages before they reach the main intent classifier or LLM.

Route blocking rules:
  off_topic    — blocked for all roles
  jailbreak    — blocked for all roles (injection, impersonation, destructive intent)
  exfiltration — blocked for non-privileged roles only; ADMIN/HR/C_LEVEL bypass
                 because bulk data access is legitimate for them
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from app.services.ai.routing.guardrails.middleware.base import Guard, GuardResult
from app.services.ai.routing.semantic_router import SemanticRouter

if TYPE_CHECKING:
    from app.models.employee import Employee

_REJECTION_MESSAGES: dict[str, str] = {
    "off_topic": (
        "I can only assist with HR-related questions — policies, employee data, "
        "or HR tasks such as leave and tickets. Please rephrase your question."
    ),
    "jailbreak": (
        "I cannot process that request. "
        "If you believe this was flagged in error, contact your HR administrator."
    ),
    "exfiltration": (
        "I cannot process that request. "
        "If you believe this was flagged in error, contact your HR administrator."
    ),
}

# Roles with legitimate access to all employee data — skip exfiltration check.
_EXFILTRATION_EXEMPT_ROLES: frozenset[str] = frozenset({"ADMIN", "HR", "C_LEVEL"})


class SemanticGuardrail(Guard):
    """
    Checks user input against guardrail routes.
    Returns a GuardResult that short-circuits the pipeline on a match.
    """

    def __init__(self, router: SemanticRouter) -> None:
        self.router = router

    def check(self, message: str, user: "Employee") -> Optional[GuardResult]:
        name, _score = self.router(message)
        if name not in _REJECTION_MESSAGES:
            return None
        # ADMIN/HR/C_LEVEL have legitimate bulk data access — skip exfiltration check.
        if name == "exfiltration" and user.role.value in _EXFILTRATION_EXEMPT_ROLES:
            return None
        return GuardResult(
            blocked=True,
            route=name,
            response=_REJECTION_MESSAGES[name],
        )
