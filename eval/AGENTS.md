---
last_compiled_date: 2026-05-12
version: 1.1
---

# eval/AGENTS.md

## Purpose

Evaluation dataset and results for the AI copilot features.
Contains eval prompts, expected behaviors, and test run outputs.

## Key Files

| File | Role |
|------|------|
| `eval/dataset.json` | Eval dataset — input prompts, roles, expected routes, expected behaviors |
| `docs/ai_eval_results.md` | Latest eval run results (203/203 test cases) |
| `docs/ai_eval_dataset.json` | Eval dataset used for the graded run |

## Eval Categories

| Category | What it tests |
|----------|--------------|
| Policy RAG | Grounded answers, correct source citations, refuse when no context |
| SQL Agent | Correct SELECT generation, forbidden column blocking, DDL rejection |
| Action Agent | Correct intent extraction, permission enforcement, service layer dispatch |
| Security | Prompt injection defense, cross-user data access attempts, unauthorized actions |
| RBAC | Role-appropriate responses for EMPLOYEE/MANAGER/ADMIN |

## Running Evals

```bash
cd backend
python scripts/run_eval.py --dataset ../eval/dataset.json --output ../docs/ai_eval_results.md
```

## Working Rules

- New AI feature → add eval cases before marking complete.
- Security test cases (prompt injection, forbidden columns, unauthorized actions) must always pass 100%.
- Do not modify eval dataset to make failing tests pass — fix the code instead.
