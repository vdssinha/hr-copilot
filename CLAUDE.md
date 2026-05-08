# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Working Style

- Always read `Requirement.md` before making major changes
- Prefer small iterative steps
- Ask before making large architectural decisions
- Never include `Co-Authored-By` or any trailer lines in commit messages


## Tech Stack

- Backend: FastAPI + SQLite + SQLAlchemy + Alembic
- AI: Anthropic Claude (claude-sonnet-4-6) + ChromaDB (local) + Voyage AI embeddings
- Frontend: Next.js (TypeScript)

## Commit Granularity (IMPORTANT)

Commits must be small and logical — one concern per commit. Never bundle a whole milestone into a single commit. Examples of correct granularity:

- `feat(ai): abstract interfaces for LLM, embedder, vector store`
- `feat(ai): Anthropic LLM provider`
- `feat(rag): policy ingestion pipeline`
- `feat(rag): retrieval and grounded answer generation`
- `feat(api): POST /api/v1/chat/policy endpoint`

Wrong: one commit for an entire milestone (e.g., "feat: Milestone 2 — Policy RAG").

## Development Workflow

Follow this strictly:

1. Work in small milestones.
2. After each milestone:
   - Ensure the code compiles.
   - Run all relevant tests.
   - Fix any failures before proceeding.
3. Only when everything is working:
   - Create a git commit with a clear message.
4. Never commit broken or untested code.
5. Stop after each milestone and then move forward after checking everything.
6. Use the devx-* skills and subagents to work in parallel.
7. all things should be configurable eg model can be changed via config not a code change.
8. everything should be plugin like strategy pattern abstract things so that changing from any vector db, etc does not require any code change just config and adding a totally new implementaiuon suppprt does not impact any existing code.




