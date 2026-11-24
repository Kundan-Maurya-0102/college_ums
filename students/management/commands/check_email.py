"""Prove that outbound e-mail really leaves this deployment.

A college admin should not have to discover a broken SMTP setup when the first
student credential mail silently vanishes. This sends one real message (or prints
the exact reason it cannot).
"""
from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Send a test e-mail and report which backend / host was actually used"

    def add_arguments(self, parser):
        parser.add_argument("to", help="recipient address, e.g. admin@college.edu")
        parser.add_argument("--dry-run", action="store_true",
                            help="only report the configuration, send nothing")

    def handle(self, *args, **options):
        to = options["to"]
        backend = settings.EMAIL_BACKEND
        console = backend.endswith("console.EmailBackend")
        locmem = backend.endswith("locmem.EmailBackend")
        filebased = backend.endswith("filebased.EmailBackend")

        self.stdout.write(f"backend      : {backend}")
        self.stdout.write(f"host:port    : {settings.EMAIL_HOST}:{settings.EMAIL_PORT}"
                          f" tls={settings.EMAIL_USE_TLS} ssl={settings.EMAIL_USE_SSL}")
        self.stdout.write(f"user         : {settings.EMAIL_HOST_USER or '(none)'}")
        self.stdout.write(f"from address : {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"recipient    : {to}")

        if not settings.EMAIL_HOST_USER and not settings.EMAIL_HOST_PASSWORD and not console:
            self.stdout.write(self.style.WARNING(
                "no SMTP credentials — most providers reject anonymous mail; "
                "set EMAIL_HOST_USER / EMAIL_HOST_PASSWORD in .env"))

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry run: nothing sent"))
            return

        if console or locmem or filebased:
            self.stdout.write(self.style.WARNING(
                f"{backend} does not deliver to the internet — "
                "the message will only be printed/stored locally"))

        subject = f"[{settings.COLLEGE_NAME}] UMS e-mail test"
        body = ("If you can read this, credential mails and subscription reminders "
                "will reach students and colleges from this deployment.")
        try:
            connection = get_connection(timeout=settings.EMAIL_TIMEOUT)
            connection.open()
            connection.close()
            sent = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to],
                             fail_silently=False, connection=connection)
        except Exception as exc:
            raise CommandError(f"e-mail failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"sent {sent} message(s) to {to}"))
