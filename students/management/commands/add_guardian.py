"""Create (or reuse) a parent/guardian account linked to one or more students.

The office runs this when a parent asks for portal access. It prints a one-time
set-password link — the account gets an unusable password until the parent uses it,
so no password is ever sent in plain text.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from students.models import GuardianProfile, StudentProfile
from students.password_links import build_set_password_link

User = get_user_model()


class Command(BaseCommand):
    help = "Link a parent/guardian to a student and print a set-password link"

    def add_arguments(self, parser):
        parser.add_argument("--student", required=True,
                            help="student registration number (repeatable)", action="append")
        parser.add_argument("--name", required=True, help="guardian's full name")
        parser.add_argument("--username", default="", help="login (default: derived from phone/name)")
        parser.add_argument("--phone", default="", help="10-digit mobile")
        parser.add_argument("--email", default="")
        parser.add_argument("--relationship", default="Parent",
                            choices=["Parent", "Guardian", "Sibling"])
        parser.add_argument("--dry-run", action="store_true", help="show what would happen")

    def handle(self, *args, **options):
        students = []
        for reg in options["student"]:
            try:
                students.append(StudentProfile.objects.get(registration_number__iexact=reg.strip()))
            except StudentProfile.DoesNotExist:
                raise CommandError(f"No student with registration number {reg!r}")

        phone = "".join(ch for ch in options["phone"] if ch.isdigit())[-10:]
        username = (options["username"] or phone or f"parent.{students[0].registration_number}").lower()

        existing = User.objects.filter(username=username).first()
        guardian = GuardianProfile.objects.filter(user=existing).first() if existing else None

        self.stdout.write(f"guardian : {options['name']} ({options['relationship']})")
        self.stdout.write(f"username : {username}")
        self.stdout.write(f"students : {', '.join(s.registration_number for s in students)}")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry run — nothing written"))
            return

        with transaction.atomic():
            if existing is None:
                existing = User.objects.create_user(username=username, password=None)
                existing.set_unusable_password()
                existing.save(update_fields=["password"])
            if guardian is None:
                guardian = GuardianProfile.objects.create(
                    user=existing, name=options["name"], phone=phone,
                    email=options["email"], relationship=options["relationship"])
            else:
                guardian.name = options["name"]
                guardian.phone = phone or guardian.phone
                guardian.email = options["email"] or guardian.email
                guardian.is_active = True
                guardian.save()
            guardian.students.add(*students)

        link = build_set_password_link(existing)
        self.stdout.write(self.style.SUCCESS(f"linked {len(students)} student(s)"))
        self.stdout.write(f"set password link (share once, expires per PASSWORD_TOKEN_TIMEOUT_HOURS):\n{link}")
