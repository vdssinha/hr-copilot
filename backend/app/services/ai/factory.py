from functools import lru_cache

from app.core.config import AI_LLM_PROVIDER, AI_EMBEDDER_PROVIDER, AI_VECTOR_STORE_PROVIDER
from app.services.ai.interfaces.llm import BaseLLMProvider
from app.services.ai.interfaces.embedder import BaseEmbedder
from app.services.ai.interfaces.vector_store import BaseVectorStore


@lru_cache(maxsize=None)
def get_llm_provider() -> BaseLLMProvider:
    if AI_LLM_PROVIDER == "anthropic":
        from app.services.ai.providers.llm.anthropic import AnthropicProvider
        return AnthropicProvider()
    if AI_LLM_PROVIDER == "openai":
        from app.services.ai.providers.llm.openai_llm import OpenAIProvider
        return OpenAIProvider()
    raise ValueError(f"Unknown LLM provider: {AI_LLM_PROVIDER!r}")


@lru_cache(maxsize=None)
def get_embedder() -> BaseEmbedder:
    if AI_EMBEDDER_PROVIDER == "voyage":
        from app.services.ai.providers.embedders.voyage import VoyageEmbedder
        return VoyageEmbedder()
    if AI_EMBEDDER_PROVIDER == "openai":
        from app.services.ai.providers.embedders.openai_embedder import OpenAIEmbedder
        return OpenAIEmbedder()
    raise ValueError(f"Unknown embedder provider: {AI_EMBEDDER_PROVIDER!r}")


@lru_cache(maxsize=None)
def get_vector_store(collection_name: str = "hr_policies") -> BaseVectorStore:
    if AI_VECTOR_STORE_PROVIDER == "chroma":
        from app.services.ai.providers.vector_stores.chroma import ChromaVectorStore
        return ChromaVectorStore(collection_name=collection_name)
    if AI_VECTOR_STORE_PROVIDER == "faiss":
        from app.services.ai.providers.vector_stores.faiss_store import FAISSVectorStore
        return FAISSVectorStore(collection_name=collection_name)
    raise ValueError(f"Unknown vector store: {AI_VECTOR_STORE_PROVIDER!r}")
