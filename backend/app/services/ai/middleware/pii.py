"""
PII masking middleware.

Replaces detected PII in user input with placeholder tokens before the message
reaches any LLM. Operates left-to-right; longer/more-specific patterns run first
to prevent partial matches (e.g. PAN matched before a generic digit sequence).

Replacements:
  [EMAIL]   — email addresses
  [PHONE]   — phone numbers (Indian +91 and generic international)
  [PAN]     — Indian PAN (e.g. ABCDE1234F)
  [AADHAAR] — Aadhaar numbers (12 digits, optionally grouped)
  [IFSC]    — Indian IFSC codes (e.g. HDFC0001234)
  [CARD]    — credit/debit card numbers (16 digits, optionally spaced/dashed)
"""
import re
from app.services.ai.middleware.base import InputTransformer

# Order matters: more-specific patterns before generic ones.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Email — before phone to avoid matching domain part as number
    ("EMAIL", re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    )),
    # Indian PAN: 5 uppercase + 4 digits + 1 uppercase (e.g. ABCDE1234F)
    ("PAN", re.compile(
        r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    )),
    # Aadhaar: exactly 12 digits in 4-4-4 groups separated by space or dash (separator required).
    # Plain 12-digit run without separators is NOT matched to avoid false-positives
    # on salary figures, timestamps, employee IDs, and other numeric data.
    ("AADHAAR", re.compile(
        r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}\b",
    )),
    # IFSC: 4 uppercase + '0' + 6 alphanumeric (e.g. HDFC0001234)
    ("IFSC", re.compile(
        r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    )),
    # Credit/debit card: 16 digits MUST have separators (space or dash) between groups of 4.
    # Unseparated 16-digit runs are too common (employee codes, order numbers) to mask blindly.
    ("CARD", re.compile(
        r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b",
    )),
    # Indian mobile: optional +91/91/0 prefix, then 10 digits starting with 6-9
    ("PHONE", re.compile(
        r"(?:\+91|91|0)?[\s\-]?[6-9]\d{9}\b",
    )),
    # Generic international phone: +<1-3 digits> (area) local
    ("PHONE", re.compile(
        r"\+?\d{1,3}[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}\b",
    )),
]


class PIIMiddleware(InputTransformer):
    """Mask all detected PII before the message reaches the LLM."""

    def transform(self, message: str) -> str:
        for label, pattern in _PATTERNS:
            message = pattern.sub(f"[{label}]", message)
        return message
