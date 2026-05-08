from typing import List, Tuple
import chromadb
from app.core.config import settings
from app.services.ai.interfaces.vector_store import BaseVectorStore, Document


class ChromaVectorStore(BaseVectorStore):
    def __init__(self, collection_name: str = "hr_policies"):
        self._client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
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
        self, query_embedding: List[float], k: int = 5
    ) -> List[Tuple[Document, float]]:
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, self._collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        )
        docs_out = []
        for content, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            docs_out.append((Document(content=content, metadata=meta), dist))
        return docs_out

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> None:
        self._collection.delete(where={"$ne": {"_id": ""}})
        name = self._collection.name
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )
