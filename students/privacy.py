"""Privacy helpers: keep personal data out of logs and error reports.

Used by:
- ``students.logging_filters.RedactSensitiveFilter`` (console/file logs)
- the optional Sentry ``before_send`` hook in ``college_ums/settings.py``
"""
import re

from django.conf import settings

# Patterns ordered from most specific to most generic.
_BASE_PATTERNS = [
    # e-mail
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    # long digit runs (aadhaar, card, account) before the shorter phone rule
    (re.compile(r"(?<!\d)\d{12,19}(?!\d)"), "[number]"),
    # phone numbers (10 digits, optional +91 / spaces / dashes)
    (re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s-]?)?\d{10}(?!\d)"), "[phone]"),
    # date of birth in common formats
    (re.compile(r"(?<!\d)\d{1,2}[/-]\d{1,2}[/-](?:19|20)\d{2}(?!\d)"), "[date]"),
    # set-password / reset tokens in URLs
    (re.compile(r"/(?:set-password|reset)/[^/\s]+/[^/\s]+"), "/[token-url]"),
    # api keys / bearer tokens in messages
    (re.compile(r"(?i)\b(?:bearer|token|api[_-]?key|secret)[\s:=]+[A-Za-z0-9._\-]{12,}"), "[secret redacted]"),
]

_PATTERNS = _BASE_PATTERNS + [
    (re.compile(pattern), "[redacted]")
    for pattern in getattr(settings, "LOG_REDACT_EXTRA_PATTERNS", []) or []
    if pattern
]

SENSITIVE_KEYS = {
    "phone", "mobile", "contact", "address", "email", "password", "passwd",
    "token", "secret", "authorization", "cookie", "session", "father_name",
    "mother_name", "date_of_birth", "dob", "aadhaar", "pan", "account_number",
    "card", "cvv", "upi", "prompt", "content", "remarks",
}


def redact_text(value):
    """Return ``value`` with e-mails, phones, tokens and long numbers masked."""
    if value is None:
        return ""
    text = str(value)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_mapping(data, depth=0):
    """Recursively redact sensitive keys and values in a dict/list payload."""
    if depth > 6:
        return "[truncated]"
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            if str(key).lower() in SENSITIVE_KEYS:
                cleaned[key] = "[redacted]"
            else:
                cleaned[key] = redact_mapping(value, depth + 1)
        return cleaned
    if isinstance(data, (list, tuple)):
        return [redact_mapping(item, depth + 1) for item in data]
    if isinstance(data, str):
        return redact_text(data)
    return data


def scrub_sentry_event(event, hint=None):
    """Sentry ``before_send`` hook: strip request bodies, cookies and PII.

    Everything a student's phone/e-mail could hide in is scrubbed: the event
    message, the log entry, the transaction name, request data/query/headers,
    ``extra``, exception values and breadcrumbs.
    """
    event.pop("user", None)

    for key in ("message", "transaction", "culprit"):
        if isinstance(event.get(key), str):
            event[key] = redact_text(event[key])

    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        for key in ("message", "formatted"):
            if isinstance(logentry.get(key), str):
                logentry[key] = redact_text(logentry[key])

    request = event.get("request") or {}
    if request.get("cookies"):
        request["cookies"] = "[redacted]"
    for key in ("data", "query_string", "env"):
        if key in request:
            request[key] = redact_mapping(request[key])
    headers = request.get("headers") or {}
    for header in ("Authorization", "Cookie", "X-CsrfToken", "X-CSRFToken"):
        if header in headers:
            headers[header] = "[redacted]"
    if request:
        event["request"] = request

    if "extra" in event:
        event["extra"] = redact_mapping(event["extra"])

    for exception in (event.get("exception") or {}).get("values", []) or []:
        if exception.get("value"):
            exception["value"] = redact_text(exception["value"])

    breadcrumbs = (event.get("breadcrumbs") or {}).get("values") or []
    for crumb in breadcrumbs:
        if isinstance(crumb.get("message"), str):
            crumb["message"] = redact_text(crumb["message"])
        if isinstance(crumb.get("data"), dict):
            crumb["data"] = redact_mapping(crumb["data"])

    return event


def scrub_breadcrumb(breadcrumb, hint=None):
    """Sentry ``before_breadcrumb`` hook."""
    if breadcrumb.get("message"):
        breadcrumb["message"] = redact_text(breadcrumb["message"])
    if isinstance(breadcrumb.get("data"), (dict, list)):
        breadcrumb["data"] = redact_mapping(breadcrumb["data"])
    return breadcrumb


def anonymize_student(profile):
    """Erase a student's personal identifiers, keeping academic/fee records.

    Returns the registration number (kept) so the caller can log it.
    Idempotent: running it twice is harmless.
    """
    reg_no = profile.registration_number

    profile.name = "Anonymised Student"
    profile.phone = ""
    profile.email = ""
    profile.address = ""
    profile.father_name = ""
    profile.mother_name = ""
    profile.date_of_birth = None
    profile.save(update_fields=[
        "name", "phone", "email", "address", "father_name", "mother_name", "date_of_birth",
    ])

    user = profile.user
    user.first_name = ""
    user.last_name = ""
    user.email = ""
    user.is_active = False
    user.username = f"anonymised-{profile.pk}"
    user.set_unusable_password()
    user.save(update_fields=["first_name", "last_name", "email", "is_active",
                             "username", "password"])
    return reg_no
