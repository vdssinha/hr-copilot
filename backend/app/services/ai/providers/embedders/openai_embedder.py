from typing import List
from openai import OpenAI
from app.core.config import settings
from app.services.ai.interfaces.embedder import BaseEmbedder


class OpenAIEmbedder(BaseEmbedder):
    def __init__(self):
        kwargs = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            kwargs["base_url"] = settings.OPENAI_BASE_URL
        self._client = OpenAI(**kwargs)
        self._model = settings.AI_EMBEDDING_MODEL

    def embed(self, texts: List[str]) -> List[List[float]]:
        resp = self._client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in resp.data]

    def embed_query(self, text: str) -> List[float]:
        resp = self._client.embeddings.create(input=[text], model=self._model)
        return resp.data[0].embedding
