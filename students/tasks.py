"""Background jobs (django-q2, ORM broker) with retries and safe fallbacks.

Heavy or flaky work — outbound WhatsApp/SMS/e-mail, big CSV imports — must never
block a web request. Tasks are queued when a worker is configured; if the queue
is unavailable the caller can run them synchronously.
"""
import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)

# Errors worth retrying: network, timeouts, 5xx from a gateway.
RETRYABLE = ("timeout", "timed out", "connection", "temporarily", "429", "502", "503", "504")


def _is_retryable(exc):
    text = str(exc).lower()
    return any(marker in text for marker in RETRYABLE)


def with_retries(func, *args, attempts=None, backoff=1.0, **kwargs):
    """Call ``func`` with bounded exponential backoff on retryable failures.

    Retries live inside the job (2s, 4s, 8s …) so behaviour is deterministic and
    does not depend on broker re-delivery timing. Permanent errors are re-raised
    immediately and never retried.
    """
    attempts = attempts or getattr(settings, "TASK_MAX_ATTEMPTS", 3)
    attempts = max(1, int(attempts))
    last_error = None
    for attempt in range(attempts):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            if not _is_retryable(exc) or attempt == attempts - 1:
                raise
            delay = backoff * (2 ** attempt)
            logger.warning("%s failed (%s); retry %d/%d in %.0fs",
                           getattr(func, "__name__", func), exc, attempt + 1, attempts, delay)
            time.sleep(delay)
    raise last_error


def enqueue(func, *args, **kwargs):
    """Queue ``func``; fall back to an inline call if the broker is down.

    Returns ("queued"|"ran"|"failed", detail).
    """
    try:
        from django_q.tasks import async_task
    except ImportError:  # django-q2 not installed (e.g. minimal deploy)
        return run_now(func, *args, **kwargs)

    try:
        # Retries come from Q_CLUSTER['max_attempts'] (django-q2 re-queues
        # failed tasks until that limit); `retry` is not a per-task option.
        task_id = async_task(func, *args, **kwargs)
    except Exception as exc:  # broker/DB problem: do the work inline instead
        logger.warning("Queue unavailable (%s); running %s inline", exc, getattr(func, "__name__", func))
        return run_now(func, *args, **kwargs)

    if task_id is None:  # Q_CLUSTER['sync'] = True
        return ("ran", "executed synchronously")
    return ("queued", task_id)


def run_now(func, *args, **kwargs):
    try:
        result = func(*args, **kwargs)
    except Exception as exc:
        logger.exception("Inline task %s failed", getattr(func, "__name__", func))
        return ("failed", str(exc)[:200])
    return ("ran", result)


# ── notification delivery ─────────────────────────────────────────────

def send_email_task(to_address, subject, body):
    """Send one e-mail. Raises on failure so django-q2 can retry."""
    from django.core.mail import send_mail

    if not to_address:
        return "skipped (no address)"
    sent = with_retries(
        send_mail,
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[to_address],
        fail_silently=False,
    )
    return f"sent ({sent})"


def _make_twilio_client(sid, token, timeout):
    """Factory kept separate so tests can patch it without twilio installed."""
    try:
        from twilio.rest import Client
    except ImportError as exc:
        raise RuntimeError("twilio package not installed") from exc
    return Client(sid, token, timeout=timeout)


def send_whatsapp_task(to_number, body, timeout=10):
    """Send a WhatsApp message through Twilio (or the college's gateway).

    Returns a status string. Raises only on retryable errors so the queue retries;
    permanent failures (missing credentials, bad number) are logged and swallowed.
    """
    sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    if not sid or not token:
        logger.info("WhatsApp skipped: credentials not configured")
        return "skipped (no credentials)"
    if not to_number:
        return "skipped (no number)"

    number = to_number.strip()
    if not number.startswith("+"):
        number = f"+91{number}"
    sender = getattr(settings, "TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    def _deliver():
        client = _make_twilio_client(sid, token, timeout)
        return client.messages.create(body=body, from_=sender, to=f"whatsapp:{number}")

    try:
        message = with_retries(_deliver)
    except Exception as exc:
        logger.error("WhatsApp delivery failed: %s", exc)
        return f"failed: {str(exc)[:80]}"
    return f"sent ({message.sid})"


def notify(channel, to, subject="", body=""):
    """Queue a notification on the right channel (email|whatsapp|sms)."""
    if channel == "email":
        return enqueue(send_email_task, to, subject, body)
    if channel in ("whatsapp", "sms"):
        text = body or subject
        return enqueue(send_whatsapp_task, to, text)
    return ("failed", f"unknown channel {channel!r}")


def send_credentials_task(profile_id):
    """WhatsApp the one-time set-password link for a freshly imported student."""
    from .models import StudentProfile
    from .whatsapp import send_whatsapp_credentials

    try:
        profile = StudentProfile.objects.select_related("user").get(pk=profile_id)
    except StudentProfile.DoesNotExist:
        return "skipped (student deleted)"
    return send_whatsapp_credentials(profile)
