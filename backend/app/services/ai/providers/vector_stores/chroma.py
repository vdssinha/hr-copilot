from typing import Dict, List, Optional, Tuple
import chromadb
from app.core.config import CHROMA_PERSIST_DIR
from app.services.ai.interfaces.vector_store import BaseVectorStore, Document


class ChromaVectorStore(BaseVectorStore):
    def __init__(self, collection_name: str = "hr_policies"):
        self._client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        # embedding_function=None: we manage embeddings externally
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, documents: List[Document], embeddings: List[List[float]]) -> None:
        ids = [str(i) for i in range(self._collection.count(), self._collection.count() + len(documents))]
        self._collection.add(
            ids=ids,
            documents=[d.content for d in documents],
            metadatas=[d.metadata for d in documents],
            embeddings=embeddings,
        )

    def similarity_search(
        self,
        query_embedding: List[float],
        k: int = 5,
        where: Optional[Dict] = None,
    ) -> List[Tuple[Document, float]]:
        total = self._collection.count()
        if total == 0:
            return []
        kwargs: Dict = {
            "query_embeddings": [query_embedding],
            "n_results": min(k, total),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        results = self._collection.query(**kwargs)
        return [
            (Document(content=content, metadata=meta), dist)
            for content, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def delete_where(self, where: Dict) -> None:
        """Delete all documents whose metadata matches the filter."""
        self._collection.delete(where=where)

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> None:
        name = self._collection.name
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )
