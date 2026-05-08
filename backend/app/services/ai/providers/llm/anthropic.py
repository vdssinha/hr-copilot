from typing import Optional
import anthropic
from app.core.config import settings
from app.services.ai.interfaces.llm import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._model = settings.AI_LLM_MODEL

    def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=kwargs.get("max_tokens", 1024),
            system=system or "You are a helpful HR assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
