"""
Embedding-based semantic router.

API mirrors the semantic-router library so swapping in the real library later
requires only changing this import — no caller changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from app.services.ai.interfaces.embedder import BaseEmbedder


@dataclass
class Route:
    name: str
    utterances: List[str]
    # populated by SemanticRouter._index(); not set by caller
    _embeddings: Optional[np.ndarray] = field(default=None, init=False, repr=False)


class SemanticRouter:
    """
    Matches a query to the closest Route by cosine similarity.

    Usage:
        router = SemanticRouter(encoder=embedder, routes=[r1, r2], threshold=0.75)
        name, score = router("How many sick days do I get?")
        # name="POLICY_QA", score=0.89
        # name=None if score < threshold (UNKNOWN)
    """

    def __init__(
        self,
        encoder: BaseEmbedder,
        routes: List[Route],
        threshold: float = 0.75,
    ) -> None:
        self.encoder = encoder
        self.routes = routes
        self.threshold = threshold
        self._index()

    def _index(self) -> None:
        for route in self.routes:
            vecs = np.array(self.encoder.embed(route.utterances), dtype=np.float32)
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            route._embeddings = vecs / np.where(norms == 0, 1.0, norms)

    def __call__(self, query: str) -> Tuple[Optional[str], float]:
        q = np.array(self.encoder.embed_query(query), dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        best_name: Optional[str] = None
        best_score: float = -1.0

        for route in self.routes:
            if route._embeddings is None:
                continue
            scores = route._embeddings @ q  # cosine sim (vectors pre-normalized)
            score = float(scores.max())
            if score > best_score:
                best_score = score
                best_name = route.name

        if best_score < self.threshold:
            return None, best_score
        return best_name, best_score
