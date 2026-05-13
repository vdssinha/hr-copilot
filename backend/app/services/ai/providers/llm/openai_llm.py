import re
from typing import Optional
from openai import OpenAI
from app.core.config import LLM_API_KEY, LLM_BASE_URL, AI_LLM_MODEL
from app.services.ai.interfaces.llm import BaseLLMProvider


def _extract_from_reasoning(reasoning: str) -> str:
    """Extract the final answer from a thinking model's reasoning_content block.

    Tries in order:
    1. Explicit answer markers: "Final Answer:", "Answer:", "**Answer**", etc.
    2. Last "Draft N:" block content.
    3. Last substantial paragraph (>50 chars) — avoids returning a section header.
    4. Last non-empty line as final fallback.
    """
    if not reasoning.strip():
        return ""

    # 1. Explicit answer section
    match = re.search(
        r"(?:final answer|answer|conclusion)[:\*\s]+(.+?)(?:\n\n|\Z)",
        reasoning, re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    # 2. Last Draft block
    drafts = re.findall(r"[*\-]?\s*Draft \d+[:\*]+\s*(.+?)(?=\n[*\-]?\s*Draft |\Z)", reasoning, re.DOTALL)
    if drafts:
        return drafts[-1].strip()

    # 3. Last substantial paragraph
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", reasoning) if len(p.strip()) > 50]
    if paragraphs:
        return paragraphs[-1]

    # 4. Last non-empty line
    lines = [l.strip() for l in reasoning.splitlines() if l.strip()]
    return lines[-1] if lines else ""


class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        kwargs = {"api_key": LLM_API_KEY}
        if LLM_BASE_URL:
            kwargs["base_url"] = LLM_BASE_URL
        self._client = OpenAI(**kwargs)
        self._model = AI_LLM_MODEL

    def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system or "You are a helpful HR assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=kwargs.get("max_tokens", 1024),
        )
        msg = resp.choices[0].message
        content = msg.content or ""
        # Thinking models (e.g. Gemma 4-31b via LM Studio) emit chain-of-thought in
        # reasoning_content and leave content empty when the token budget is consumed
        # by reasoning before output begins. Extract the answer from reasoning.
        if not content.strip():
            content = _extract_from_reasoning(getattr(msg, "reasoning_content", None) or "")
        return content
