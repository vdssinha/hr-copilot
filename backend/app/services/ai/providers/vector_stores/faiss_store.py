from typing import Dict, List, Optional, Tuple
from app.services.ai.interfaces.vector_store import BaseVectorStore, Document


class FAISSVectorStore(BaseVectorStore):
    """FAISS-backed vector store. Requires faiss-cpu: pip install faiss-cpu"""

    def __init__(self, collection_name: str = "hr_policies"):
        try:
            import faiss  # noqa
            import numpy as np  # noqa
        except ImportError as e:
            raise ImportError("Install faiss-cpu to use FAISSVectorStore") from e
        import faiss
        import numpy as np
        self._faiss = faiss
        self._np = np
        self._collection_name = collection_name
        self._index = None
        self._documents: List[Document] = []

    def add_documents(self, documents: List[Document], embeddings: List[List[float]]) -> None:
        vecs = self._np.array(embeddings, dtype="float32")
        if self._index is None:
            self._index = self._faiss.IndexFlatIP(vecs.shape[1])
        self._faiss.normalize_L2(vecs)
        self._index.add(vecs)
        self._documents.extend(documents)

    def similarity_search(
        self,
        query_embedding: List[float],
        k: int = 5,
        where: Optional[Dict] = None,
    ) -> List[Tuple[Document, float]]:
        if self._index is None or self._index.ntotal == 0:
            return []
        q = self._np.array([query_embedding], dtype="float32")
        self._faiss.normalize_L2(q)
        # FAISS has no native metadata filter — fetch more candidates then post-filter
        fetch_k = min(k * 10 if where else k, self._index.ntotal)
        distances, indices = self._index.search(q, fetch_k)
        results = [(self._documents[i], float(distances[0][j])) for j, i in enumerate(indices[0]) if i >= 0]
        if where:
            results = [
                (doc, dist) for doc, dist in results
                if _matches_where(doc.metadata, where)
            ]
        return results[:k]

    def delete_where(self, where: Dict) -> None:
        """Remove documents matching the metadata filter (in-memory rebuild)."""
        keep = [doc for doc in self._documents if not _matches_where(doc.metadata, where)]
        self.clear()
        if keep:
            # Embeddings are not stored — caller must re-ingest after deletion
            self._documents = keep

    def count(self) -> int:
        return self._index.ntotal if self._index else 0

    def clear(self) -> None:
        self._index = None
        self._documents = []


def _matches_where(metadata: dict, where: Dict) -> bool:
    """Minimal ChromaDB-compatible where-filter evaluation for FAISS post-filtering."""
    for key, condition in where.items():
        value = metadata.get(key)
        if isinstance(condition, dict):
            for op, operand in condition.items():
                if op == "$eq" and value != operand:
                    return False
                elif op == "$in" and value not in operand:
                    return False
                elif op == "$ne" and value == operand:
                    return False
        else:
            if value != condition:
                return False
    return True
