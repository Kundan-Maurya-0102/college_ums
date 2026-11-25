"""Daily error summary for the platform owner (super admin).

Cron (on the college deployment, 07:00):
    0 7 * * * cd /opt/ums/<slug> && .venv/bin/python manage.py send_error_digest

Only rows from the window (default 24h) are reported, so a quiet day sends either
nothing (`--only-if-errors`, the cron default) or a one-line "all quiet" note.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from students.models import ErrorEvent
from students.tasks import notify

User = get_user_model()


class Command(BaseCommand):
    help = "E-mail a summary of ERROR/CRITICAL events to the super admin(s)"

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24, help="window in hours")
        parser.add_argument("--to", action="append", default=[],
                            help="override recipients (repeatable)")
        parser.add_argument("--dry-run", action="store_true", help="print, do not send")
        parser.add_argument("--only-if-errors", action="store_true",
                            help="send nothing when the window is clean (cron default)")
        parser.add_argument("--include-resolved", action="store_true")

    def recipients(self, options):
        if options["to"]:
            return options["to"]
        configured = getattr(settings, "SUPPORT_EMAIL", "") or ""
        if configured:
            return [configured]
        return list(User.objects.filter(is_superuser=True, is_active=True)
                    .exclude(email="").values_list("email", flat=True).distinct())

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(hours=options["hours"])
        events = ErrorEvent.objects.filter(last_seen__gte=since)
        if not options["include_resolved"]:
            events = events.filter(is_resolved=False)
        events = events.order_by("-count", "-last_seen")

        total = events.count()
        occurrences = sum(events.values_list("count", flat=True))
        self.stdout.write(f"window: last {options['hours']}h | distinct errors: {total} "
                          f"| occurrences: {occurrences}")

        if not total:
            self.stdout.write(self.style.SUCCESS("no errors in the window"))
            if options["only_if_errors"]:
                return

        lines = [
            f"College UMS error digest — {settings.COLLEGE_NAME}",
            f"Window: last {options['hours']} hours",
            f"Distinct problems: {total}, total occurrences: {occurrences}",
            "",
        ]
        for event in events[:40]:
            lines.append(f"[{event.level}] x{event.count} — {event.last_seen:%Y-%m-%d %H:%M}")
            lines.append(f"  logger : {event.logger_name}")
            if event.path:
                lines.append(f"  path   : {event.path}")
            lines.append(f"  message: {event.message[:300]}")
            lines.append("")
        if total > 40:
            lines.append(f"... and {total - 40} more rows — open /admin-panel/system-status/.")

        lines += [
            "",
            "Actions:",
            "  1. Open /admin-panel/system-status/ for storage, jobs and backup state.",
            "  2. Mark a row resolved after fixing it (Django admin -> Error events).",
            "  3. If the database or jobs are involved, run: manage.py diagnose_college <domain>",
        ]
        body = "\n".join(lines)
        subject = (f"[{settings.COLLEGE_NAME}] {total} error(s) in the last "
                   f"{options['hours']}h ({occurrences} occurrences)")

        if options["dry_run"]:
            self.stdout.write("--- dry run, not sent ---")
            self.stdout.write(body)
            return

        recipients = self.recipients(options)
        if not recipients:
            self.stdout.write(self.style.WARNING(
                "no recipients: set SUPPORT_EMAIL, add an e-mail to a superuser, or pass --to"))
            return

        for address in recipients:
            status = notify("email", address, subject, body)
            self.stdout.write(f"queued to {address}: {status}")
        self.stdout.write(self.style.SUCCESS(f"digest sent to {len(recipients)} recipient(s)"))
