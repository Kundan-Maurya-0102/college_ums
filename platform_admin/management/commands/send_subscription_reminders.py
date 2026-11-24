"""Queue renewal e-mails for colleges whose subscription is expiring/expired."""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from platform_admin.models import College
from students import tasks


class Command(BaseCommand):
    help = "Email college contacts about expiring subscriptions (dry-run by default)"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="actually queue the e-mails")
        parser.add_argument("--days", type=int,
                            default=getattr(settings, "SUBSCRIPTION_REMINDER_DAYS", 14))

    def handle(self, *args, **options):
        today = timezone.localdate()
        cutoff = today + timezone.timedelta(days=options["days"])
        targets = (College.objects.exclude(status=College.STATUS_SUSPENDED)
                   .filter(subscription_expires_on__isnull=False)
                   .filter(subscription_expires_on__lte=cutoff)
                   .select_related("plan"))
        if not targets:
            self.stdout.write("No college needs a reminder today.")
            return
        college_name = getattr(settings, "COLLEGE_NAME", "") or "College UMS platform"
        for college in targets:
            days = (college.subscription_expires_on - today).days
            state = "expired" if days < 0 else f"expires in {days} day(s)"
            subject = f"[{college_name}] Subscription {state} for {college.name}"
            body = (
                f"Hello {college.name},\n\n"
                f"Your {college.plan.name if college.plan else 'UMS'} subscription "
                f"{state} (date: {college.subscription_expires_on}).\n"
                "After expiry the portal becomes read-only until renewal.\n\n"
                f"Contact {college_name} support to renew.\n"
            )
            self.stdout.write(f"{college.slug}: {state} -> {college.contact_email or 'no email'}")
            if options["apply"] and college.contact_email:
                status = tasks.notify("email", college.contact_email, subject, body)
                self.stdout.write(f"  queued: {status}")
