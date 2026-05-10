"""
Abstract base classes for the guardrail middleware pipeline.

InputTransformer  — mutates the message (e.g. PII masking). Never short-circuits.
Guard             — inspects the (possibly transformed) message and may reject it.
GuardResult       — carries the rejection payload when a Guard fires.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.employee import Employee


@dataclass(frozen=True)
class GuardResult:
    blocked: bool
    route: str      # which guardrail fired ("off_topic", "harmful", …)
    response: str   # user-facing rejection message


class InputTransformer(ABC):
    @abstractmethod
    def transform(self, message: str) -> str: ...


class Guard(ABC):
    @abstractmethod
    def check(self, message: str, user: "Employee") -> Optional[GuardResult]: ...
