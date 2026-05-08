"""
Live-backend integration test configuration.
All values overridable via env vars — no code changes needed to target staging or CI.

    INTEGRATION_BASE_URL=http://staging:8000 pytest tests/integration/
"""
import csv
import os
from pathlib import Path

BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:8000")

USERS: dict[str, dict] = {
    "admin": {
        "email":          os.getenv("INTEGRATION_ADMIN_EMAIL", "priya.sharma@novaworks.in"),
        "password":       os.getenv("INTEGRATION_ADMIN_PASS",  "Admin@1234"),
        "employee_code":  os.getenv("INTEGRATION_ADMIN_CODE",  "NW-001"),
        "name":           "Priya Sharma",
    },
    "manager": {
        "email":          os.getenv("INTEGRATION_MGR_EMAIL",   "arjun.mehta@novaworks.in"),
        "password":       os.getenv("INTEGRATION_MGR_PASS",    "Manager@1234"),
        "employee_code":  os.getenv("INTEGRATION_MGR_CODE",    "NW-002"),
        "name":           "Arjun Mehta",
        "direct_reports": ["NW-004"],
    },
    "employee": {
        "email":          os.getenv("INTEGRATION_EMP_EMAIL",   "rahul.verma@novaworks.in"),
        "password":       os.getenv("INTEGRATION_EMP_PASS",    "Employee@1234"),
        "employee_code":  os.getenv("INTEGRATION_EMP_CODE",    "NW-004"),
        "name":           "Rahul Verma",
        "manager_code":   "NW-002",
    },
}

RESTRICTED_MARKER = "[RESTRICTED]"
SKIP_INGEST = os.getenv("INTEGRATION_SKIP_INGEST", "0") == "1"

# ── HR CSV data loaded at import time ──────────────────────────────────────────
# Provides actual salary/field values so tests don't hardcode them.
# Path relative to repo root; falls back gracefully if CSV not found.
_CSV_PATH = Path(__file__).parent.parent.parent / "data" / "hr" / "hr_data.csv"

HR_CSV: dict[str, dict] = {}  # employee_id → full CSV row

if _CSV_PATH.exists():
    with open(_CSV_PATH, newline="", encoding="utf-8") as _f:
        for _row in csv.DictReader(_f):
            HR_CSV[_row["employee_id"].strip()] = {k: v.strip() for k, v in _row.items()}


def hr_field(employee_code: str, field: str) -> str:
    """Return a field value from the HR CSV for a given employee_code."""
    row = HR_CSV.get(employee_code, {})
    return row.get(field, "")
