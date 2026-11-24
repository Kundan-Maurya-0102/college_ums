"""Subscription enforcement for a college deployment.

A college deployment sets ``COLLEGE_SLUG`` in its .env. If the platform record
for that slug is suspended or expired, writes are refused with a branded
read-only page; reads keep working so students can still see their data and the
college can renew. Platform admins and Django superusers are never blocked.
"""
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

logger = logging.getLogger(__name__)

SAFE_METHODS = ("GET", "HEAD", "OPTIONS", "TRACE")
# Paths that must stay writable so an expired college can log in and support itself.
ALWAYS_ALLOWED_PREFIXES = (
    "/login", "/logout", "/set-password", "/admin/", "/healthz/", "/static/",
    "/media/", "/privacy/", "/terms/", "/platform/",
)
CACHE_KEY = "platform:college-state:{slug}"


def _college_state(slug):
    cached = cache.get(CACHE_KEY.format(slug=slug))
    if cached is not None:
        return cached
    state = None
    try:
        from .models import College

        college = College.objects.filter(slug=slug).only(
            "status", "subscription_expires_on", "name").first()
        if college:
            state = {
                "status": college.status,
                "read_only": college.is_read_only,
                "name": college.name,
            }
    except Exception:  # platform tables absent (college-only deployment)
        logger.debug("Platform tables unavailable; subscription check skipped")
        state = None
    cache.set(CACHE_KEY.format(slug=slug), state or {}, 30)
    return state or None


class SubscriptionStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        slug = getattr(settings, "COLLEGE_SLUG", "")
        if slug:
            state = _college_state(slug)
            request.college_subscription = state
            if (state and state.get("read_only") and request.method not in SAFE_METHODS
                    and not self._is_exempt(request)):
                from django.shortcuts import render

                return render(request, "read_only.html",
                              {"college_name": state.get("name") or settings.COLLEGE_NAME},
                              status=403)
        return self.get_response(request)

    @staticmethod
    def _is_exempt(request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            from .models import platform_admin_required

            if user.is_superuser or platform_admin_required(user):
                return True
        return request.path.startswith(ALWAYS_ALLOWED_PREFIXES)
