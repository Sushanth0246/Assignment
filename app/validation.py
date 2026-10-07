"""Recipient-level validation.

Request-level problems (empty list, missing course, bad date) are rejected with
422 by Pydantic. Problems with an *individual* recipient are NOT allowed to
reject the whole request: the recipient is stored as a failed certificate with a
reason, and the valid ones still get generated.
"""
import re
from typing import Any

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_NAME_LEN = 100
MAX_EMAIL_LEN = 254


def validate_recipient(raw: Any) -> tuple[dict | None, str | None]:
    """Return (clean_recipient, None) if valid, else (None, error_message)."""
    if not isinstance(raw, dict):
        return None, "Recipient must be an object with 'name' and 'email'"

    errors = []

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name is required and must be a non-empty string")
    elif len(name.strip()) > MAX_NAME_LEN:
        errors.append(f"name must be at most {MAX_NAME_LEN} characters")

    email = raw.get("email")
    if not isinstance(email, str) or not email.strip():
        errors.append("email is required and must be a non-empty string")
    elif len(email.strip()) > MAX_EMAIL_LEN or not EMAIL_RE.match(email.strip()):
        errors.append("email is not a valid email address")

    if errors:
        return None, "; ".join(errors)
    return {"name": name.strip(), "email": email.strip()}, None
