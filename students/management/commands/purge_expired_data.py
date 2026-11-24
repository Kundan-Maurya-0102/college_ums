"""Retention job: anonymise students past the retention window, prune logs.

Usage:
    python manage.py purge_expired_data                 # dry run (safe default)
    python manage.py purge_expired_data --apply         # actually anonymise/prune
    python manage.py purge_expired_data --apply --years 5 --audit-days 365
    python manage.py purge_expired_data --apply --archive-dir /mnt/archive

Cron (monthly, 3 AM on the 1st):
    0 3 1 * * cd /opt/ums/<slug> && .venv/bin/python manage.py purge_expired_data --apply
"""
import json
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from students.models import AuditLog, StudentProfile, WebsiteVisit
from students.privacy import anonymize_student


class Command(BaseCommand):
    help = "Anonymise students outside the data-retention window and prune old logs/visits."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Actually modify data (default is a dry run).")
        parser.add_argument("--years", type=int, default=None,
                            help="Retention window in years (default DATA_RETENTION_YEARS).")
        parser.add_argument("--audit-days", type=int, default=None,
                            help="Audit-log retention in days (default AUDIT_LOG_RETENTION_DAYS).")
        parser.add_argument("--visit-days", type=int, default=None,
                            help="Website visit retention in days (default VISIT_RETENTION_DAYS).")
        parser.add_argument("--archive-dir", default="",
                            help="Write an anonymised academic JSON archive per student before erasing.")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        years = options["years"] or getattr(settings, "DATA_RETENTION_YEARS", 7)
        audit_days = options["audit_days"] or getattr(settings, "AUDIT_LOG_RETENTION_DAYS", 365 * 7)
        visit_days = options["visit_days"] or getattr(settings, "VISIT_RETENTION_DAYS", 180)

        now = timezone.now()
        cutoff_year = now.year - years
        candidates = StudentProfile.objects.select_related("user").filter(
            user__is_active=True,
        ).filter(
            # graduated: admission year older than the window, or (no admission year) created long ago
            models_q(cutoff_year, now - timedelta(days=365 * years))
        ).order_by("pk")

        self.stdout.write(f"Retention window: {years} years (before {cutoff_year}).")
        self.stdout.write(f"Students eligible for anonymisation: {candidates.count()}")

        for profile in candidates:
            self.stdout.write(
                f"  - {profile.registration_number} (admitted {profile.year_of_admission or '-'})"
            )
            if not apply_changes:
                continue
            self._archive(profile, options["archive_dir"])
            reg_no = anonymize_student(profile)
            log_action_safe("retention.anonymize", profile, f"reg {reg_no}, window {years}y")

        old_audit = AuditLog.objects.filter(created_at__lt=now - timedelta(days=audit_days))
        old_visits = WebsiteVisit.objects.filter(visited_at__lt=now - timedelta(days=visit_days))
        self.stdout.write(f"Audit rows older than {audit_days} days: {old_audit.count()}")
        self.stdout.write(f"Visit rows older than {visit_days} days: {old_visits.count()}")

        if apply_changes:
            deleted_audit = old_audit.delete()[0]
            deleted_visits = old_visits.delete()[0]
            self.stdout.write(self.style.SUCCESS(
                f"Pruned {deleted_audit} audit rows and {deleted_visits} visit rows."
            ))
            self.stdout.write(self.style.SUCCESS("Retention run complete."))
        else:
            self.stdout.write(self.style.WARNING("Dry run — nothing changed. Re-run with --apply."))

    # ── helpers ────────────────────────────────────────────────────────
    def _archive(self, profile, archive_dir):
        if not archive_dir:
            return
        from pathlib import Path

        target = Path(archive_dir)
        target.mkdir(parents=True, exist_ok=True)
        payload = {
            "registration_number": profile.registration_number,
            "branch": profile.branch,
            "semester": profile.semester,
            "year_of_admission": profile.year_of_admission,
            "archived_at": timezone.now().isoformat(),
            "internal_marks": list(profile.internalexam_set.values(
                "subject__subject_code", "exam_type", "marks_obtained", "max_marks")),
            "fee_payments": list(profile.fee_payments.values(
                "fee_structure__fee_type", "amount_paid", "payment_date", "status", "receipt_number")),
        }
        out = target / f"student-{profile.registration_number}.json"
        out.write_text(json.dumps(payload, indent=2, default=str))
        self.stdout.write(f"    archived -> {out}")


def models_q(cutoff_year, cutoff_datetime):
    """Students whose admission year is past the window (fallback: created_at)."""
    from django.db.models import Q

    return Q(year_of_admission__lte=cutoff_year, year_of_admission__isnull=False) | Q(
        year_of_admission__isnull=True, created_at__lt=cutoff_datetime
    )


def log_action_safe(action, obj, detail):
    from students.audit import log_action

    class _Req:
        user = None
        META = {}

    log_action(_Req(), action, obj, detail)
