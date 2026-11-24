"""Push this college's metrics to the platform owner's API.

Runs on the *college* deployment (cron, hourly):
  COLLEGE_SLUG=abc PLATFORM_URL=https://platform.example.com \\
  PLATFORM_METRICS_TOKEN=... python manage.py report_college_metrics
"""
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from students.models import StudentProfile


def _dir_size(path):
    import os

    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


class Command(BaseCommand):
    help = "Report student count / storage / activity to the platform API"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        slug = getattr(settings, "COLLEGE_SLUG", "")
        token = getattr(settings, "PLATFORM_METRICS_TOKEN", "")
        base = getattr(settings, "PLATFORM_URL", "")
        if not slug:
            raise CommandError("COLLEGE_SLUG is not set for this deployment")
        if not base and not options["dry_run"]:
            raise CommandError("PLATFORM_URL is not set")

        last_login = (User.objects.filter(last_login__isnull=False)
                      .order_by("-last_login").values_list("last_login", flat=True).first())
        payload = {
            "student_count": StudentProfile.objects.count(),
            "active_users_30d": User.objects.filter(
                last_login__gte=timezone.now() - timezone.timedelta(days=30)).count(),
            "storage_bytes": _dir_size(str(settings.MEDIA_ROOT)),
            "last_login_at": last_login.isoformat() if last_login else None,
        }
        self.stdout.write(json.dumps(payload))
        if options["dry_run"]:
            return
        if not token:
            raise CommandError("PLATFORM_METRICS_TOKEN is not set")
        base = base or "http://localhost:8000"

        if not base.startswith(("http://", "https://")):
            raise CommandError("PLATFORM_URL must start with http:// or https://")
        request = urllib.request.Request(
            f"{base.rstrip('/')}/platform/metrics/{slug}/",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-Platform-Token": token},
            method="POST",
        )
        # Bandit B310: the URL scheme is validated above, so only http(s) is passed.
        try:
            with urllib.request.urlopen(  # nosec B310
                    request, timeout=getattr(settings, "HTTP_TIMEOUT", 10)) as resp:
                self.stdout.write(self.style.SUCCESS(f"reported: {resp.read().decode()[:200]}"))
        except urllib.error.URLError as exc:
            raise CommandError(f"report failed: {exc}") from exc
