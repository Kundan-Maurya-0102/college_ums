"""Security helpers: login throttling, client IP, upload validation."""
import hashlib
import os
import time

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError


# ── client ip ───────────────────────────────────────────────────────────
def client_ip(request):
    """Return the caller IP, honouring proxy headers only when configured.

    `X-Forwarded-For` is client-controlled and must not be trusted unless the
    app really sits behind a reverse proxy (Caddy in our deploy stack).
    """
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "")[:45]


# ── login throttling (brute force protection) ───────────────────────────
def _throttle_key(request, username):
    raw = f"{client_ip(request)}|{(username or '').strip().lower()}"
    return "login-fail:" + hashlib.sha256(raw.encode()).hexdigest()[:40]


def login_lockout_remaining(request, username):
    """Seconds left on the lockout, or 0 when the caller may try again."""
    key = _throttle_key(request, username)
    data = cache.get(key)
    if not data:
        return 0
    window = getattr(settings, "LOGIN_LOCKOUT_SECONDS", 900)
    elapsed = time.time() - data.get("first", time.time())
    remaining = int(window - elapsed)
    return max(remaining, 0) if data.get("count", 0) >= _limit() else 0


def register_login_failure(request, username):
    key = _throttle_key(request, username)
    data = cache.get(key) or {"count": 0, "first": time.time()}
    data["count"] += 1
    data["last"] = time.time()
    cache.set(key, data, getattr(settings, "LOGIN_LOCKOUT_SECONDS", 900))
    return data["count"]


def reset_login_failures(request, username):
    cache.delete(_throttle_key(request, username))


def _limit():
    return getattr(settings, "LOGIN_MAX_ATTEMPTS", 5)


# ── upload validation ───────────────────────────────────────────────────
BLOCKED_EXTENSIONS = {
    "exe", "bat", "cmd", "com", "cpl", "dll", "js", "jse", "lnk", "msi",
    "ps1", "scr", "vbs", "vbe", "wsf", "wsh", "jar", "sh", "php", "php3",
    "php4", "php5", "phtml", "py", "rb", "pl", "asp", "aspx", "jsp", "cgi",
    "htaccess", "htpasswd", "svg", "html", "htm", "xhtml",
}


def safe_upload_name(name, fallback="upload"):
    """Strip directories and risky characters from an uploaded file name."""
    base = os.path.basename((name or "").replace("\\", "/"))
    stem, dot, ext = base.rpartition(".")
    if not dot:
        stem, ext = base, ""
    stem = "".join(ch for ch in stem if ch.isalnum() or ch in "-_ ").strip()
    stem = stem.replace(" ", "-")[:80] or fallback
    ext = "".join(ch for ch in ext if ch.isalnum()).lower()
    return f"{stem}.{ext}" if ext else stem


def validate_upload(file, allowed_extensions, max_mb=None, label="File"):
    """Reject dangerous extensions, oversize files and empty uploads.

    Returns the sanitised file name (also assigned back to ``file.name``).
    """
    if not file:
        return None
    name = file.name or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext in BLOCKED_EXTENSIONS:
        raise ValidationError(f"{label}: .{ext} files are not allowed.")
    allowed = {item.lower().lstrip(".") for item in allowed_extensions}
    if ext not in allowed:
        pretty = ", ".join(sorted("." + item for item in allowed))
        raise ValidationError(f"{label} must be one of: {pretty}.")

    max_mb = max_mb or getattr(settings, "CSV_MAX_UPLOAD_MB", 5)
    if file.size and file.size > max_mb * 1024 * 1024:
        raise ValidationError(f"{label} size must be under {max_mb} MB.")
    if file.size == 0:
        raise ValidationError(f"{label} is empty.")

    file.name = safe_upload_name(name, fallback=label.lower().replace(" ", "-"))
    return file.name


IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx",
                       "txt", "csv", "zip"}


def rate_limit_hit(request, bucket, limit, window_seconds):
    """Sliding-window counter in the cache. Returns True when the caller is over the limit."""
    from django.core.cache import cache

    ident = f"user:{getattr(getattr(request, 'user', None), 'pk', None)}|ip:{client_ip(request)}"
    key = f"rl:{bucket}:{ident}"
    count = cache.get(key, 0)
    if count >= limit:
        return True
    # add() keeps the original TTL for the window
    cache.add(key, 0, window_seconds)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, window_seconds)
    return False
