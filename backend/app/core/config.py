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

# ── AI Generation Token Limits ────────────────────────────────────────────────
# Correlation map (must hold when tuning any value):
#
#   SMART_COPILOT_INTENT  ≥  SQL_AGENT_QUERY
#       Reasoning models consume thinking tokens before output. Intent output
#       is tiny (~100 tokens JSON) but thinking can exceed 200 tokens, so the
#       budget must be larger than a raw-generation task like SQL.
#
#   SQL_AGENT_QUERY  ≈  2× SQL_AGENT_SUMMARY
#       The query itself can be complex (JOINs, subqueries ~300 tokens);
#       the summary is always 1-2 sentences (~100 tokens). Half is enough.
#
#   POLICY_RAG_ANSWER  =  HR_DATA_RAG_ANSWER
#       Both produce multi-paragraph prose answers with source citations.
#       Keep in sync — diverging them creates inconsistent answer depth.
#
#   POLICY_RAG_ANSWER  ≈  2× SQL_AGENT_QUERY
#       Prose answers need more space than generated SQL.
#
#   ACTION_AGENT_EXTRACT  =  POLICY_RAG_ANSWER
#       Tool-call JSON with nested parameters can be as long as a prose answer.
#
#   ACTION_AGENT_SUMMARY  ≈  0.5× ACTION_AGENT_EXTRACT
#       Post-action summary is always brief; half the extraction budget.

# Used in: router_agent.py — LLM call that classifies user intent into
#   POLICY_QA / SQL_QUERY / HR_ACTION / UNKNOWN.
#   Must be ≥ SMART_COPILOT_INTENT (see correlation above).
#   Raised from 128 → 512 because reasoning models (e.g. Gemma 4-31b)
#   spend 100-300 thinking tokens before emitting the ~100-token JSON output.
AI_MAX_TOKENS_SMART_COPILOT_INTENT = int(os.getenv("AI_MAX_TOKENS_SMART_COPILOT_INTENT", "512"))

# Used in: sql_agent.py — LLM call that generates the SQL SELECT statement.
#   SQL queries are short (~50-300 tokens). 512 covers complex JOINs.
#   Must be ≤ SMART_COPILOT_INTENT (see correlation above).
#   Must be ≈ 2× SQL_AGENT_SUMMARY.
AI_MAX_TOKENS_SQL_AGENT_QUERY = int(os.getenv("AI_MAX_TOKENS_SQL_AGENT_QUERY", "512"))

# Used in: sql_agent.py — LLM call that summarises SQL result rows in plain English.
#   Output is always 1-2 sentences; 256 is generous.
#   Must be ≈ 0.5× SQL_AGENT_QUERY (see correlation above).
AI_MAX_TOKENS_SQL_AGENT_SUMMARY = int(os.getenv("AI_MAX_TOKENS_SQL_AGENT_SUMMARY", "256"))

# Used in: policy_rag.py — LLM call that answers HR policy questions from
#   retrieved document chunks. Multi-paragraph answers with citations need room.
#   Must equal HR_DATA_RAG_ANSWER and ≈ 2× SQL_AGENT_QUERY (see correlations).
AI_MAX_TOKENS_POLICY_RAG_ANSWER = int(os.getenv("AI_MAX_TOKENS_POLICY_RAG_ANSWER", "1024"))

# Used in: hr_data_rag.py — LLM call that answers questions over HR employee
#   data. Same answer format as POLICY_RAG_ANSWER; keep in sync.
#   Must equal POLICY_RAG_ANSWER (see correlation above).
AI_MAX_TOKENS_HR_DATA_RAG_ANSWER = int(os.getenv("AI_MAX_TOKENS_HR_DATA_RAG_ANSWER", "1024"))

# Used in: action_agent.py — LLM call that extracts structured tool-call JSON
#   from the user message (intent + parameters). Nested JSON can be verbose.
#   Must equal POLICY_RAG_ANSWER (see correlation above).
AI_MAX_TOKENS_ACTION_AGENT_EXTRACT = int(os.getenv("AI_MAX_TOKENS_ACTION_AGENT_EXTRACT", "1024"))

# Used in: action_agent.py — LLM call that summarises the action result in
#   plain English after execution. Always brief.
#   Must be ≈ 0.5× ACTION_AGENT_EXTRACT (see correlation above).
AI_MAX_TOKENS_ACTION_AGENT_SUMMARY = int(os.getenv("AI_MAX_TOKENS_ACTION_AGENT_SUMMARY", "500"))

# ── Conversation Memory ───────────────────────────────────────────────────────
# Prior conversation turns (user+assistant pairs) sent to ALL agents so they
# can resolve references like "her", "that project", etc. from recent context.
AI_CONTEXT_TURNS = int(os.getenv("AI_CONTEXT_TURNS", "3"))
