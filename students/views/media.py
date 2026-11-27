"""Serve uploaded files through Django instead of the web server.

Why: `deploy/Caddyfile` used to expose `/srv/media` directly, so anyone with a URL
(and CSV uploads contain names, registration numbers and phone numbers) could read
student data. Now every request passes a login check, the CSV inbox is staff-only,
and a path that escapes MEDIA_ROOT is rejected.

Performance note: Django streams these files, which is slower than Caddy. That is a
deliberate trade (files are small PDFs/images). If media volume grows, move to
object storage with signed URLs and set MEDIA_PROTECTED=False.
"""
import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import redirect

# Directories that hold personal data: staff only.
STAFF_ONLY_PREFIXES = ("csv_uploads/",)


def _safe_path(path):
    """Resolve `path` inside MEDIA_ROOT or raise 404 (blocks .. and absolute paths)."""
    media_root = os.path.realpath(settings.MEDIA_ROOT)
    target = os.path.realpath(os.path.join(media_root, path))
    if not (target == media_root or target.startswith(media_root + os.sep)):
        raise Http404("File not found")
    if not os.path.isfile(target):
        raise Http404("File not found")
    return target


def serve_media(request, path):
    if not request.user.is_authenticated:
        from django.utils.http import urlencode
        return redirect(f"{settings.LOGIN_URL}?{urlencode({'next': request.path})}")

    normalised = path.replace("\\", "/").lstrip("/")
    if normalised.startswith(tuple(STAFF_ONLY_PREFIXES)) and not (
        request.user.is_staff or request.user.is_superuser
    ):
        raise Http404("File not found")

    target = _safe_path(normalised)
    content_type, _ = mimetypes.guess_type(target)
    return FileResponse(open(target, "rb"), content_type=content_type or "application/octet-stream")
