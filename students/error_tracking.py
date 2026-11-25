"""Turn ERROR/CRITICAL log records into rows the admin can actually see.

Why a logging handler and not a middleware: an unhandled exception in a view is
logged by `django.request` (level ERROR) and never reaches middleware response code,
and a failure in a background job never passes through a view at all. A handler sees
both.

Rules:
  * only ERROR and CRITICAL are stored (WARNING stays in the log files);
  * same logger + message + path updates one row and increments `count`, so a
    crashed loop cannot flood the table;
  * the message is truncated, and writing is wrapped in try/except — a broken
    logging sink must never take the request down with it.
"""
import hashlib
import logging

MAX_MESSAGE = 1000


def fingerprint_for(logger_name, message, path):
    raw = f'{logger_name}|{path}|{message[:300]}'
    return hashlib.sha256(raw.encode('utf-8', 'ignore')).hexdigest()[:40]


class DatabaseErrorHandler(logging.Handler):
    """Store ERROR/CRITICAL records in `students.ErrorEvent`."""

    def emit(self, record):
        try:
            if record.levelno < logging.ERROR:
                return
            from django.conf import settings

            if not getattr(settings, 'ERROR_TRACKING_ENABLED', True):
                return

            from django.utils import timezone

            from .models import ErrorEvent

            path = ''
            request = getattr(record, 'request', None)
            if request is not None:
                try:
                    path = request.path[:300]
                except Exception:  # noqa: BLE001 - path is best effort
                    path = ''
            if not path:
                path = getattr(record, 'pathname', '') or ''

            message = (record.getMessage() or record.name)[:MAX_MESSAGE]
            fingerprint = fingerprint_for(record.name, message, path)
            now = timezone.now()
            event, created = ErrorEvent.objects.get_or_create(
                fingerprint=fingerprint,
                defaults={
                    'level': record.levelname[:10],
                    'logger_name': record.name[:120],
                    'message': message,
                    'path': path[:300],
                    'first_seen': now,
                    'last_seen': now,
                    'count': 1,
                },
            )
            if not created:
                # F() keeps concurrent workers from losing increments.
                from django.db.models import F

                ErrorEvent.objects.filter(pk=event.pk).update(
                    count=F('count') + 1, last_seen=now,
                    level=record.levelname[:10],
                )
        except Exception:  # noqa: BLE001 - never let logging break the app
            self.handleError(record)
