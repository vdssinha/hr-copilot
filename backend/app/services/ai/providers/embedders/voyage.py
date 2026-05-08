from typing import List
import voyageai
from app.core.config import EMBEDDER_API_KEY, AI_EMBEDDING_MODEL
from app.services.ai.interfaces.embedder import BaseEmbedder


class VoyageEmbedder(BaseEmbedder):
    def __init__(self):
        self._client = voyageai.Client(api_key=EMBEDDER_API_KEY)
        self._model = AI_EMBEDDING_MODEL

    def embed(self, texts: List[str]) -> List[List[float]]:
        result = self._client.embed(texts, model=self._model, input_type="document")
        return result.embeddings

    def embed_query(self, text: str) -> List[float]:
        result = self._client.embed([text], model=self._model, input_type="query")
        return result.embeddings[0]
