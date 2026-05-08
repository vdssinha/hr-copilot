"""
Cold-call test configuration.

All values are overridable via environment variables so the suite can target
any running instance (local dev, staging, CI) without code changes.

Example:
    COLD_CALL_BASE_URL=http://staging:8000 pytest tests/cold_call/
"""
import os

BASE_URL = os.getenv("COLD_CALL_BASE_URL", "http://localhost:8000")

# Per-role credentials — override via env to run against a different dataset.
USERS: dict[str, dict] = {
    "admin": {
        "email":         os.getenv("COLD_CALL_ADMIN_EMAIL",    "priya.sharma@novaworks.in"),
        "password":      os.getenv("COLD_CALL_ADMIN_PASS",     "Admin@1234"),
        "employee_code": os.getenv("COLD_CALL_ADMIN_CODE",     "NW-001"),
        "name":          "Priya Sharma",
    },
    "manager": {
        "email":         os.getenv("COLD_CALL_MGR_EMAIL",      "arjun.mehta@novaworks.in"),
        "password":      os.getenv("COLD_CALL_MGR_PASS",       "Manager@1234"),
        "employee_code": os.getenv("COLD_CALL_MGR_CODE",       "NW-002"),
        "name":          "Arjun Mehta",
        # employees whose manager_id == this code in hr_data.csv
        "direct_reports": ["NW-004"],
    },
    "employee": {
        "email":         os.getenv("COLD_CALL_EMP_EMAIL",      "rahul.verma@novaworks.in"),
        "password":      os.getenv("COLD_CALL_EMP_PASS",       "Employee@1234"),
        "employee_code": os.getenv("COLD_CALL_EMP_CODE",       "NW-004"),
        "name":          "Rahul Verma",
        "manager_code":  "NW-002",
    },
}

# Sensitive fields the LLM must redact when access is denied
SENSITIVE_FIELDS = ["salary", "date_of_birth", "phone", "1200000", "1950000"]
RESTRICTED_MARKER = "[RESTRICTED]"
