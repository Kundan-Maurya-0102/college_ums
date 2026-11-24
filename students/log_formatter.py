"""Structured JSON log formatter.

`LOG_FORMAT=json` switches the console handler to one JSON object per line so
log shippers (Loki/CloudWatch/Papertrail) can index fields instead of regex-ing
free text. Student PII never reaches this formatter: `RedactSensitiveFilter`
runs first and replaces e-mails/phones/tokens.
"""
import datetime
import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.datetime.fromtimestamp(record.created, datetime.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "environment": getattr(record, "environment", None),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key in ("request_id", "path", "method", "status", "user", "duration_ms", "ip"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.__dict__.get("extra_fields"):
            payload.update(record.extra_fields)
        return json.dumps(payload, default=str, ensure_ascii=False)


class ContextFilter(logging.Filter):
    """Attach the environment name to every record (cheap, one place)."""

    def __init__(self, environment="development"):
        super().__init__()
        self.environment = environment

    def filter(self, record):
        if getattr(record, "environment", None) is None:
            record.environment = self.environment
        return True
