"""Logging filter that masks personal data before it reaches any handler."""
import logging

from .privacy import redact_text


class RedactSensitiveFilter(logging.Filter):
    """Redact e-mails, phone numbers, tokens and long IDs from log records."""

    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:  # malformed record; let other handlers deal with it
            return True
        redacted = redact_text(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True
