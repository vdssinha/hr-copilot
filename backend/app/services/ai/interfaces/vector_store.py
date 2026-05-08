from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Document:
    content: str
    metadata: dict = field(default_factory=dict)


class BaseVectorStore(ABC):
    @abstractmethod
    def add_documents(self, documents: List[Document], embeddings: List[List[float]]) -> None: ...

    @abstractmethod
    def similarity_search(
        self,
        query_embedding: List[float],
        k: int = 5,
        where: Optional[Dict] = None,
    ) -> List[Tuple[Document, float]]: ...

    @abstractmethod
    def delete_where(self, where: Dict) -> None:
        """Delete all documents matching the metadata filter."""
        ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def clear(self) -> None: ...
