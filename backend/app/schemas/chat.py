from typing import List, Literal, Optional
from pydantic import BaseModel


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[HistoryMessage] = []
    session_id: Optional[str] = None  # frontend-generated UUID; enables Tier 2/3 memory
