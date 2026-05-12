---
last_compiled_date: 2026-05-12
version: 1.1
---

# frontend/AGENTS.md

## Purpose

Next.js (TypeScript) frontend for CB Nest HRMS + AI Copilot.
JWT-authenticated SPA. All backend calls go through `lib/api.ts`.

## Key Files

| File | Role |
|------|------|
| `app/ai-copilot/page.tsx` | Main AI copilot page — mode selector + chat UI |
| `app/layout.tsx` | Root layout with collapsible sidebar navigation |
| `app/login/page.tsx` | Login form + JWT storage |
| `components/ai/ChatPanel.tsx` | Message input + chat history display |
| `components/ai/SourceList.tsx` | Policy RAG source citations |
| `components/ai/SQLResultTable.tsx` | Tabular SQL query results |
| `components/ai/ActionResultCard.tsx` | HR action confirmation/result |
| `components/ai/PendingApprovals.tsx` | Manager-only pending leave approvals |
| `components/ai/MyLeaves.tsx` | Employee own leave history |
| `components/ai/MyProjects.tsx` | Own project assignments |
| `components/ai/MyTickets.tsx` | Own tickets |
| `components/ai/Announcements.tsx` | Announcement feed |
| `lib/api.ts` | API client — wraps fetch, attaches Bearer JWT |
| `lib/auth.ts` | JWT storage + decode (role extraction) |

## Chat Modes

The AI copilot supports these modes (mapped to backend endpoints):
- `router` → `/api/v1/chat/router` (auto-classifies intent)
- `policy` → `/api/v1/chat/policy`
- `sql` → `/api/v1/chat/sql`
- `actions` → `/api/v1/chat/actions`
- `hr-data` → `/api/v1/chat/hr-data`

## RBAC in Frontend

Frontend uses JWT role for **UI display only** (show/hide tabs, menu items).
**All actual authorization is enforced by the backend.**
Never gate data access on frontend role alone.

RBAC rules from JWT:
- `EMPLOYEE` — own data only; no approve/assign/announce
- `MANAGER` — team data + approve leave + assign tickets + announce
- `ADMIN` — all data + admin panel

## Working Rules

- All API calls go through `lib/api.ts` — never use raw `fetch` with hardcoded URLs.
- Role-based UI elements: use the role from the decoded JWT, but treat as display hint only.
- Never store sensitive data (salary, bank, PAN) in frontend state.
- Chat modes: each mode maps to a specific backend endpoint — do not mix response schemas.
- Keep edits localized to this module unless the change explicitly crosses the API boundary.

## Validation

```bash
cd frontend
npm run build    # TypeScript type check + Next.js build
npm run lint     # ESLint
```

## Dev Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```
