# Tech Stack — NovaWorks PeopleOps Copilot

## Backend

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI (Python 3.11+) |
| ORM | SQLAlchemy 2.x |
| DB | SQLite (`cbnest.db` / `hr.db`) |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt |
| Package mgr | uv / pip |

## AI Layer

| Component | Technology |
|-----------|-----------|
| LLM (default) | OpenAI-compatible (LM Studio / OpenAI API) |
| LLM (alt) | Anthropic Claude (claude-sonnet-4-6) |
| Embedder (default) | OpenAI embeddings / nomic-embed-text |
| Embedder (alt) | Voyage AI (voyageai) |
| Vector store (default) | ChromaDB (local) |
| Vector store (alt) | FAISS |
| Chunking | LangChain RecursiveCharacterTextSplitter (800 chars / 100 overlap) |

## Frontend

| Component | Technology |
|-----------|-----------|
| Framework | Next.js 14+ (TypeScript) |
| Styling | Tailwind CSS |
| Build | Next.js app router |

## Dev Tools

| Tool | Purpose |
|------|---------|
| pytest | Backend unit tests |
| uvicorn | ASGI server |
| alembic | Schema migrations |
| npm | Frontend dependencies |
