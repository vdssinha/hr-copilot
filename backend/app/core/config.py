"""Single source of truth for all configuration.

Change ONE variable to swap a provider — no other code changes needed.
All provider routing, API key resolution, and base URLs are decided here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM Provider ─────────────────────────────────────────────────────────────
# Options: "anthropic" | "openai"
#
# "openai" works with OpenAI API, LM Studio, or any OpenAI-compatible endpoint.
# Set OPENAI_BASE_URL=http://localhost:1234/v1 for LM Studio.

AI_LLM_PROVIDER = os.getenv("AI_LLM_PROVIDER", "anthropic")
AI_LLM_MODEL    = os.getenv("AI_LLM_MODEL",    "claude-sonnet-4-6")

_LLM_SETTINGS = {
    "anthropic": {"api_key_env": "ANTHROPIC_API_KEY", "base_url": None},
    "openai":    {"api_key_env": "OPENAI_API_KEY",    "base_url": os.getenv("OPENAI_BASE_URL") or None},
}
LLM_API_KEY  = os.getenv(_LLM_SETTINGS[AI_LLM_PROVIDER]["api_key_env"], "")
LLM_BASE_URL = _LLM_SETTINGS[AI_LLM_PROVIDER]["base_url"]

# ── Embedder Provider ─────────────────────────────────────────────────────────
# Options: "voyage" | "openai"
#
# "voyage" uses Voyage AI (api.voyageai.com); falls back to ANTHROPIC_API_KEY
#          if VOYAGE_API_KEY is not set.
# "openai" uses OpenAI or any OpenAI-compatible endpoint (respects OPENAI_BASE_URL).

AI_EMBEDDER_PROVIDER = os.getenv("AI_EMBEDDER_PROVIDER", "voyage")
AI_EMBEDDING_MODEL   = os.getenv("AI_EMBEDDING_MODEL",   "voyage-3")

_EMBEDDER_SETTINGS = {
    "voyage": {"api_key_env": "VOYAGE_API_KEY"},
    "openai": {"api_key_env": "OPENAI_API_KEY"},
}
EMBEDDER_API_KEY  = os.getenv(_EMBEDDER_SETTINGS[AI_EMBEDDER_PROVIDER]["api_key_env"], "") \
                    or os.getenv("ANTHROPIC_API_KEY", "")  # voyage falls back to Anthropic key
EMBEDDER_BASE_URL = os.getenv("OPENAI_BASE_URL") or None   # used only when provider=openai

# ── Vector Store ──────────────────────────────────────────────────────────────
# Options: "chroma" | "faiss"

AI_VECTOR_STORE_PROVIDER = os.getenv("AI_VECTOR_STORE_PROVIDER", "chroma")
CHROMA_PERSIST_DIR       = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cbnest.db")

# ── JWT ───────────────────────────────────────────────────────────────────────
SECRET_KEY                  = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM                   = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# ── File paths ────────────────────────────────────────────────────────────────
POLICY_UPLOAD_DIR = os.getenv("POLICY_UPLOAD_DIR", "./data/policies")
BACKEND_BASE_URL  = os.getenv("BACKEND_BASE_URL",  "http://localhost:8000")

# ── App ───────────────────────────────────────────────────────────────────────
APP_ENV   = os.getenv("APP_ENV",   "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
