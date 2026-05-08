from typing import Optional
from openai import OpenAI
from app.core.config import settings
from app.services.ai.interfaces.llm import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        kwargs = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            kwargs["base_url"] = settings.OPENAI_BASE_URL
        self._client = OpenAI(**kwargs)
        self._model = settings.AI_LLM_MODEL

    def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system or "You are a helpful HR assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=kwargs.get("max_tokens", 1024),
        )
        return resp.choices[0].message.content
