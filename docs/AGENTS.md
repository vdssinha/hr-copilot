---
last_compiled_date: 2026-05-12
version: 1.0
discovery_generated: true
---

# docs/AGENTS.md

## Purpose
- design, architecture, ADRs, and user-facing implementation doctrine.

## Key Files
- `docs/ai_architecture.md`
- `docs/ai_eval_dataset.json`
- `docs/ai_eval_results.md`
- `docs/ai_permissions_matrix.md`
- `docs/backend/INDEX.md`
- `docs/backend/OVERVIEW.md`

## Working Rules
- Keep edits localized to this module unless the change explicitly crosses boundaries.
- Update adjacent docs or tests when the module contract changes.

## Validation
- `backend/tests/conftest.py`
- `backend/tests/__init__.py`
- `backend/tests/unit/__init__.py`
- `backend/tests/unit/test_prompt_injection_defense.py`
