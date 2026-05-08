#!/usr/bin/env python3
"""
Run all live-backend integration tests in one shot.

The backend server must be running before calling this script.
This script checks the health endpoint first and exits immediately
with a clear error if the server is not up.

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
    --tb=short  traceback style
"""
import os
import sys
import subprocess
import urllib.request
import urllib.error

BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:8000")

SUITES = [
    "tests/integration/auth/",
    "tests/integration/rag/",
    "tests/integration/sql/",
    "tests/integration/actions/",
]

DEFAULT_FLAGS = ["-v", "--tb=short"]


def _check_server() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=5) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def main() -> int:
    print(f"Checking backend at {BASE_URL} ...")
    if not _check_server():
        print(
            f"\n[ERROR] Backend not reachable at {BASE_URL}/health\n"
            f"Start the server first:\n"
            f"  cd backend && uv run --env-file .env uvicorn app.main:app --reload\n"
            f"Then re-run this script."
        )
        return 1

    print(f"Backend up. Running integration test suites.\n")
    extra_flags = sys.argv[1:]
    cmd = [sys.executable, "-m", "pytest"] + SUITES + DEFAULT_FLAGS + extra_flags
    print(f"Command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
