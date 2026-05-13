"""
GuardrailPipeline — production-grade middleware chain for the HR Copilot.

Execution order for every incoming message:

  1. InputTransformers  (PII masking, normalisation, …) — mutate message in order
  2. Guards             (semantic guardrail) — first match short-circuits with rejection
  3. route_and_answer() — normal intent routing + agent dispatch

The pipeline exposes a lazy singleton via get_pipeline() so the embedder and
guardrail SemanticRouter are indexed exactly once at first request.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.services.ai.routing.guardrails.middleware.base import Guard, GuardResult, InputTransformer


class GuardrailPipeline:
    def __init__(
        self,
        transformers: List[InputTransformer] = None,
        guards: List[Guard] = None,
    ) -> None:
        self.transformers: List[InputTransformer] = transformers or []
        self.guards: List[Guard] = guards or []

    def preprocess(self, message: str, user: Employee) -> Tuple[str, Optional[GuardResult]]:
        """
        Run PII transforms then guard checks.
        Returns (processed_message, GuardResult) where GuardResult is non-None on rejection.
        Used by both run() and the streaming path so logic stays in one place.
        """
        processed = message
        for t in self.transformers:
            processed = t.transform(processed)
        for guard in self.guards:
            result = guard.check(processed, user)
            if result and result.blocked:
                return processed, result
        return processed, None

    def run(
        self,
        db: Session,
        user: Employee,
        message: str,
        history: list = None,
        session_id: str = None,
    ) -> dict:
        processed, blocked = self.preprocess(message, user)

        if blocked:
            return {
                "route": {
                    "intent": "BLOCKED",
                    "confidence": 1.0,
                    "reason": f"Guardrail triggered: {blocked.route}",
                    "router": "guardrail",
                },
                "result": {"answer": blocked.response},
                "guardrail": blocked.route,
            }

        from app.services.ai.routing.router_agent import route_and_answer
        return route_and_answer(db, user, processed, history=history, session_id=session_id)


@lru_cache(maxsize=1)
def get_pipeline() -> GuardrailPipeline:
    """
    Lazy singleton.  Embedder and guardrail router are built once on first call.
    Add / remove middleware here — no changes needed in endpoints.
    """
    from app.services.ai import factory as _factory
    from app.services.ai.routing.guardrails.routes import ALL_GUARDRAIL_ROUTES
    from app.services.ai.routing.guardrails.middleware.guardrail import SemanticGuardrail
    from app.services.ai.routing.guardrails.middleware.pii import PIIMiddleware
    from app.services.ai.routing.semantic_router import SemanticRouter
    from app.core.config import AI_GUARDRAIL_THRESHOLD

    guardrail_router = SemanticRouter(
        encoder=_factory.get_embedder(),
        routes=ALL_GUARDRAIL_ROUTES,
        threshold=AI_GUARDRAIL_THRESHOLD,
    )

    return GuardrailPipeline(
        transformers=[PIIMiddleware()],
        guards=[SemanticGuardrail(guardrail_router)],
    )
