"""
3-tier conversation memory service.

Tier 1 — User Profile   : cross-session, cross-agent, persistent user facts.
Tier 2 — Session Context: within-session, cross-agent. Carries source_agent provenance.
Tier 3 — Agent Working  : within-session, agent-local. Cleared into Tier 2 at threshold.

Privacy contract:
  - Tier 1 and 2 must never contain sensitive values (salary, PII, credentials).
  - Tier 3 content is agent-local; other agents never read it.
  - Summaries written by LLM are validated against this rule before storage.
"""
import json
import re
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import (
    AI_CONTEXT_MAX_MEMORY_ITEMS,
    AI_CONTEXT_MEMORY_TTL_HOURS,
    AI_CONTEXT_SUMMARIZE_THRESHOLD,
    AI_MAX_TOKENS_MEMORY_EXTRACT,
)
from app.models.conversation_memory import ConversationMemory, MemoryTier
from app.services.ai import factory as _factory

# ── Sensitive keywords — extracted facts containing these are discarded ────────
_SENSITIVE_TERMS = frozenset({
    "salary", "wage", "pay", "bank", "account", "ifsc", "pan", "password",
    "date_of_birth", "dob", "phone", "credit", "debit",
})

_EXTRACT_SYSTEM = """You are a memory extraction agent for an HR assistant system.

Your job is to identify durable, reusable facts from conversation excerpts that will improve future interactions.

----------------------
CORE BEHAVIOR
----------------------

1. Extract Durable Facts
   - Only extract facts useful in a future conversation: role, department, preferences, manager name, recurring patterns.
   - Skip transient details: what was asked this specific turn, intermediate steps, query results.

2. Privacy Gate
   - Never include salary figures, bank details, passwords, dates of birth, PAN, or phone numbers.
   - If stating a fact requires a sensitive value, omit the fact entirely.

3. Conciseness
   - Each fact must be one sentence.
   - Return an empty list if nothing worth retaining exists.

----------------------
DECISION RULE
----------------------

- Durable, non-sensitive fact → include
- Fact requires sensitive value → exclude
- Nothing useful → return []

Respond ONLY with a JSON array of strings.
Example: ["Works in Engineering department", "Prefers casual leave", "Manager is Alice"]"""

_SUMMARIZE_SYSTEM = """You are a conversation summarizer for an HR assistant.

Your job is to compress conversation history into a brief, factual summary for future context.

----------------------
CORE BEHAVIOR
----------------------

1. Compress Faithfully
   - Capture what the user asked, what actions were taken, and what was resolved.
   - Aim for 3-5 sentences maximum.

2. Omit Noise
   - Skip pleasantries, filler, repeated questions, and back-and-forth clarifications.

3. Privacy Gate
   - Never include salary figures, PAN, bank details, or phone numbers in the summary.

----------------------
DECISION RULE
----------------------

- Substantive exchange → summarize factually in 3-5 sentences
- Only pleasantries or no decisions made → one sentence or omit

Respond with plain text — no JSON, no bullet points."""


# ── Internal helpers ──────────────────────────────────────────────────────────

def _expiry() -> Optional[datetime]:
    if AI_CONTEXT_MEMORY_TTL_HOURS == 0:
        return None
    return datetime.utcnow() + timedelta(hours=AI_CONTEXT_MEMORY_TTL_HOURS)


def _is_safe(text: str) -> bool:
    lower = text.lower()
    return not any(term in lower for term in _SENSITIVE_TERMS)


def _parse_json_list(raw: str) -> List[str]:
    raw = raw.strip()
    raw = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip("` \n")
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return [str(x) for x in result if x]
    except (json.JSONDecodeError, ValueError):
        pass
    return []


def _active_filter(query, model):
    """Filter out expired memories."""
    return query.filter(
        (model.expires_at == None) | (model.expires_at > datetime.utcnow())  # noqa: E711
    )


# ── Read ──────────────────────────────────────────────────────────────────────

def load_tier1(db: Session, user_id: int) -> List[str]:
    """Load user profile facts (Tier 1). No session or agent filter."""
    rows = _active_filter(
        db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id,
            ConversationMemory.tier == MemoryTier.USER_PROFILE,
        ),
        ConversationMemory,
    ).order_by(ConversationMemory.created_at.desc()).limit(AI_CONTEXT_MAX_MEMORY_ITEMS).all()
    return [r.content for r in rows]


def load_tier2(db: Session, user_id: int, session_id: str) -> List[str]:
    """Load session context (Tier 2). Cross-agent, includes provenance tag."""
    if not session_id:
        return []
    rows = _active_filter(
        db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id,
            ConversationMemory.session_id == session_id,
            ConversationMemory.tier == MemoryTier.SESSION,
        ),
        ConversationMemory,
    ).order_by(ConversationMemory.created_at.desc()).limit(AI_CONTEXT_MAX_MEMORY_ITEMS).all()
    # Include provenance so agents know where the fact came from
    return [
        f"[{r.source_agent}] {r.content}" if r.source_agent else r.content
        for r in rows
    ]


def load_tier3(db: Session, user_id: int, session_id: str, agent_name: str) -> List[str]:
    """Load agent working memory (Tier 3). Agent-local only."""
    if not session_id:
        return []
    rows = _active_filter(
        db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id,
            ConversationMemory.session_id == session_id,
            ConversationMemory.agent_name == agent_name,
            ConversationMemory.tier == MemoryTier.AGENT,
        ),
        ConversationMemory,
    ).order_by(ConversationMemory.created_at.desc()).limit(AI_CONTEXT_MAX_MEMORY_ITEMS).all()
    return [r.content for r in rows]


def build_memory_section(
    db: Session,
    user_id: int,
    session_id: Optional[str],
    agent_name: str,
) -> str:
    """
    Build the {memory_section} block injected into every system prompt.

    Returns empty string when no memory exists (no prompt bloat).
    """
    t1 = load_tier1(db, user_id)
    t2 = load_tier2(db, user_id, session_id or "") if session_id else []
    t3 = load_tier3(db, user_id, session_id or "", agent_name) if session_id else []

    if not t1 and not t2 and not t3:
        return ""

    lines = ["[Memory]"]
    if t1:
        lines.append("User profile:")
        lines.extend(f"  - {x}" for x in t1)
    if t2:
        lines.append("Session context:")
        lines.extend(f"  - {x}" for x in t2)
    if t3:
        lines.append("Your working notes:")
        lines.extend(f"  - {x}" for x in t3)

    return "\n".join(lines)


# ── Write ─────────────────────────────────────────────────────────────────────

def _store(
    db: Session,
    user_id: int,
    tier: MemoryTier,
    content: str,
    session_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    source_agent: Optional[str] = None,
) -> None:
    if not _is_safe(content):
        return
    db.add(ConversationMemory(
        user_id=user_id,
        session_id=session_id,
        agent_name=agent_name,
        tier=tier,
        content=content,
        source_agent=source_agent,
        expires_at=None if tier == MemoryTier.USER_PROFILE else _expiry(),
    ))
    db.commit()


# ── Summarization ─────────────────────────────────────────────────────────────

def _count_agent_turns(db: Session, user_id: int, session_id: str, agent_name: str) -> int:
    return db.query(ConversationMemory).filter(
        ConversationMemory.user_id == user_id,
        ConversationMemory.session_id == session_id,
        ConversationMemory.agent_name == agent_name,
        ConversationMemory.tier == MemoryTier.AGENT,
    ).count()


def maybe_summarize(
    db: Session,
    user_id: int,
    session_id: Optional[str],
    agent_name: str,
    history: list,
) -> None:
    """
    Fire when agent-local history exceeds AI_CONTEXT_SUMMARIZE_THRESHOLD turns.

    1. Summarize oldest history turns → store as Tier 2 (session, cross-agent).
    2. Extract durable user facts from history → store as Tier 1 (user profile).
    3. Clear Tier 3 agent entries for this session (replaced by Tier 2 summary).
    """
    if not session_id:
        return

    turn_count = len(history) // 2  # each pair = 1 turn
    if turn_count < AI_CONTEXT_SUMMARIZE_THRESHOLD:
        return

    llm = _factory.get_llm_provider()

    # Build history text for LLM
    history_text = "\n".join(
        f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}"
        for m in history
    )

    # 1. Summarize into Tier 2
    summary = llm.generate(
        history_text,
        system=_SUMMARIZE_SYSTEM,
        max_tokens=AI_MAX_TOKENS_MEMORY_EXTRACT,
    ).strip()

    if summary and _is_safe(summary):
        _store(
            db, user_id,
            tier=MemoryTier.SESSION,
            content=summary,
            session_id=session_id,
            source_agent=agent_name,
        )

    # 2. Extract Tier 1 user profile facts
    facts_raw = llm.generate(
        history_text,
        system=_EXTRACT_SYSTEM,
        max_tokens=AI_MAX_TOKENS_MEMORY_EXTRACT,
    )
    facts = _parse_json_list(facts_raw)
    for fact in facts[:AI_CONTEXT_MAX_MEMORY_ITEMS]:
        if _is_safe(fact):
            _store(db, user_id, tier=MemoryTier.USER_PROFILE, content=fact)

    # 3. Clear Tier 3 for this agent+session (now promoted to Tier 2)
    db.query(ConversationMemory).filter(
        ConversationMemory.user_id == user_id,
        ConversationMemory.session_id == session_id,
        ConversationMemory.agent_name == agent_name,
        ConversationMemory.tier == MemoryTier.AGENT,
    ).delete()
    db.commit()


def store_agent_turn(
    db: Session,
    user_id: int,
    session_id: Optional[str],
    agent_name: str,
    content: str,
) -> None:
    """
    Store a notable observation from the current agent turn as Tier 3.
    Called by agents when they identify something worth remembering locally
    (e.g. 'user is applying SICK leave', 'last SQL query was about project Alpha').
    """
    if not session_id:
        return
    _store(
        db, user_id,
        tier=MemoryTier.AGENT,
        content=content,
        session_id=session_id,
        agent_name=agent_name,
    )
