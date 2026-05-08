from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Document:
    content: str
    metadata: dict = field(default_factory=dict)


class BaseVectorStore(ABC):
    @abstractmethod
    def add_documents(self, documents: List[Document], embeddings: List[List[float]]) -> None: ...

    @abstractmethod
    def similarity_search(
        self, query_embedding: List[float], k: int = 5
    ) -> List[Tuple[Document, float]]: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def clear(self) -> None: ...
