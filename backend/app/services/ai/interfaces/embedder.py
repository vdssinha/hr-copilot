from abc import ABC, abstractmethod
from typing import List


class BaseEmbedder(ABC):
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> List[float]: ...

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a potentially large list of texts, batching as needed.

        Default: single call to embed(). Providers with per-call limits override this.
        """
        return self.embed(texts)
