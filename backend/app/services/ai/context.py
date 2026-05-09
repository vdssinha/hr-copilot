"""Shared conversation-context utilities for all AI agents."""
from app.core.config import AI_CONTEXT_TURNS


def build_history_block(history: list, max_turns: int = AI_CONTEXT_TURNS) -> str:
    """Return a formatted prior-conversation block for injection into LLM prompts.

    Trims to the last `max_turns` user+assistant pairs so token usage stays bounded.
    Returns an empty string when there is no history.
    """
    if not history:
        return ""
    trimmed = history[-(max_turns * 2):]
    lines = [f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in trimmed]
    return (
        "Prior conversation (use only to resolve references like 'her', 'that project' — "
        "do NOT re-execute previous queries):\n"
        + "\n".join(lines)
        + "\n\nCurrent message:"
    )
