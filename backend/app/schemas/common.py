from typing import Any, Optional
from pydantic import BaseModel


class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, data: Any = None) -> "APIResponse":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "APIResponse":
        return cls(success=False, error=error)
