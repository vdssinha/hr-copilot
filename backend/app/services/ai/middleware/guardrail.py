"""
Semantic guardrail middleware.

Uses a SemanticRouter loaded with off_topic and harmful routes to detect
and reject messages before they reach the main intent classifier or any LLM.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from app.services.ai.middleware.base import Guard, GuardResult
from app.services.ai.semantic_router import SemanticRouter

if TYPE_CHECKING:
    from app.models.employee import Employee

_REJECTION_MESSAGES: dict[str, str] = {
    "off_topic": (
        "I can only assist with HR-related questions — policies, employee data, "
        "or HR tasks such as leave and tickets. Please rephrase your question."
    ),
    "harmful": (
        "I cannot process that request. "
        "If you believe this was flagged in error, contact your HR administrator."
    ),
}


class SemanticGuardrail(Guard):
    """
    Checks user input against guardrail routes (off_topic, harmful).
    Returns a GuardResult that short-circuits the pipeline on a match.
    """

    def __init__(self, router: SemanticRouter) -> None:
        self.router = router

    def check(self, message: str, user: "Employee") -> Optional[GuardResult]:
        name, _score = self.router(message)
        if name in _REJECTION_MESSAGES:
            return GuardResult(
                blocked=True,
                route=name,
                response=_REJECTION_MESSAGES[name],
            )
        return None
