from django.utils import timezone

from .models import WebsiteVisit


class WebsiteVisitMiddleware:
    """Track page visits and approximate time spent using the previous request gap."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(("/static/", "/media/", "/admin/jsi18n/")):
            return response
        if response.status_code >= 400:
            return response

        now = timezone.now()
        last_visit_id = request.session.get("last_visit_id")
        last_seen = request.session.get("last_seen_at")
        if last_visit_id and last_seen:
            try:
                last_dt = timezone.datetime.fromisoformat(last_seen)
                if timezone.is_naive(last_dt):
                    last_dt = timezone.make_aware(last_dt)
                duration = min(max(int((now - last_dt).total_seconds()), 0), 1800)
                WebsiteVisit.objects.filter(pk=last_visit_id).update(duration_seconds=duration)
            except Exception:
                pass

        visit = WebsiteVisit.objects.create(
            path=request.path[:255],
            user=request.user if request.user.is_authenticated else None,
            session_key=request.session.session_key or "",
            ip_address=self._client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
        )
        request.session["last_visit_id"] = visit.id
        request.session["last_seen_at"] = now.isoformat()
        return response

    def _client_ip(self, request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
