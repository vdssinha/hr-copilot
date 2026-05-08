#!/usr/bin/env python3
"""
Run all live-backend integration tests in one shot.

Usage (from backend/ directory):
    uv run --env-file .env python tests/integration/run_all.py

Override target server or credentials via env:
    INTEGRATION_BASE_URL=http://staging:8000 \
    INTEGRATION_SKIP_INGEST=1 \
    uv run --env-file .env python tests/integration/run_all.py

Flags forwarded to pytest:
    -v          verbose output
    -x          stop on first failure
    -k EXPR     filter tests by keyword  e.g. -k "rbac or auth"
    --tb short  traceback style
"""
import sys
import subprocess


SUITES = [
    "tests/integration/auth/",
    "tests/integration/rag/",
    "tests/integration/sql/",
    "tests/integration/actions/",
]

DEFAULT_FLAGS = ["-v", "--tb=short"]


def main() -> int:
    extra_flags = sys.argv[1:]  # forward any extra args (e.g. -x, -k "auth")
    cmd = [sys.executable, "-m", "pytest"] + SUITES + DEFAULT_FLAGS + extra_flags
    print(f"Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
