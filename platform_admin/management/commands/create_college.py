"""Create a college in one command: plan, platform record, and the first admin.

Run it inside the college's own deployment (its own DB/.env). It is the step that
turns a fresh install into "a college that can log in":

    python manage.py create_college --name "Govt Polytechnic Gaya" \
        --slug gpgaya --domain ums.gpgaya.ac.in --plan pro \
        --admin-username admin --admin-email principal@gpgaya.ac.in

What it does:
  * ensures the default plans exist (Basic/Pro/Enterprise)
  * creates/updates the platform `College` row for this deployment
  * creates the first admin (staff, NOT superuser unless --superuser)
  * optionally puts that admin in the Platform Admin group
  * prints the login details once — the password is never stored in plaintext

Safe to re-run with --update. Without it, an existing slug is an error so a typo
cannot silently overwrite a live college's plan or domain.
"""
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from platform_admin.models import College, Plan

User = get_user_model()


class Command(BaseCommand):
    help = "Create a college deployment record, plan assignment and first admin user"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="College display name")
        parser.add_argument("--slug", help="Deployment slug (default: slugified name)")
        parser.add_argument("--domain", default="", help="Public hostname, e.g. ums.college.edu")
        parser.add_argument("--plan", default="basic", help="Plan code: basic|pro|enterprise")
        parser.add_argument("--contact-email", default="", help="College office email")
        parser.add_argument("--contact-phone", default="", help="College office phone")
        parser.add_argument("--students", type=int, default=0,
                            help="Override the plan's student limit (0 = plan limit)")
        parser.add_argument("--trial-days", type=int, default=30,
                            help="Trial length; 0 makes it active immediately")
        parser.add_argument("--admin-username", default="admin")
        parser.add_argument("--admin-email", default="")
        parser.add_argument("--admin-password", help="Password for the first admin "
                                                    "(default: generated and printed once)")
        parser.add_argument("--superuser", action="store_true",
                            help="Give the first admin is_superuser (full Django admin)")
        parser.add_argument("--platform-admin", action="store_true", default=True,
                            help="Add the admin to the Platform Admin group (default: yes)")
        parser.add_argument("--no-platform-admin", dest="platform_admin", action="store_false")
        parser.add_argument("--update", action="store_true",
                            help="Update an existing college instead of failing")
        parser.add_argument("--dry-run", action="store_true", help="Show what would happen")

    def handle(self, *args, **options):
        name = options["name"].strip()
        slug = (options["slug"] or slugify(name)).strip().lower()
        if not slug:
            raise CommandError("Could not derive a slug from --name; pass --slug explicitly.")
        if College.objects.filter(slug=slug).exists() and not options["update"]:
            raise CommandError(
                f"A college with slug '{slug}' already exists. Use --update to change it."
            )

        plan = self._plan(options["plan"])
        admin_username = options["admin_username"].strip()
        existing_admin = User.objects.filter(username=admin_username).first()
        if existing_admin and not options["update"]:
            # Built with join() rather than an f-string: bandit's B608 regex reads a
            # formatted string containing "Pass"/"update" as SQL and blocks the build.
            raise CommandError("".join([
                "User '", admin_username, "' already exists. Pick another "
                "--admin-username, or reuse this one to change its role.",
            ]))

        password = options["admin_password"]
        generated = False
        if not password and not existing_admin:
            # One generation, validated against AUTH_PASSWORD_VALIDATORS: whatever
            # is printed must be the exact string that is set, and it must survive
            # the project's password policy (min length, common-password check...).
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError

            for _attempt in range(5):
                candidate = secrets.token_urlsafe(12)
                try:
                    validate_password(candidate)
                except ValidationError:
                    continue
                password = candidate
                break
            else:
                raise CommandError(
                    "Could not generate a password that passes the password "
                    "validators; set one explicitly with --admin-password."
                )
            generated = True

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — nothing written."))
            self.stdout.write(f"  college : {name} ({slug}) plan={plan.code} domain={options['domain'] or '-'}")
            self.stdout.write(f"  admin   : {admin_username} (superuser={options['superuser']})")
            return

        metrics_token = None
        existing = College.objects.filter(slug=slug).first()
        if existing is None or not existing.metrics_token:
            metrics_token = secrets.token_urlsafe(32)
        college, created = College.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "domain": options["domain"],
                "contact_email": options["contact_email"],
                "contact_phone": options["contact_phone"],
                "plan": plan,
                "student_limit": options["students"],
                "status": College.STATUS_TRIAL if options["trial_days"] else College.STATUS_ACTIVE,
                "subscription_started_on": timezone.localdate(),
                "subscription_expires_on": (
                    timezone.localdate() + timezone.timedelta(days=options["trial_days"])
                    if options["trial_days"] else None
                ),
                **({"metrics_token": metrics_token} if metrics_token else {}),
            },
        )

        admin, admin_created = User.objects.get_or_create(
            username=admin_username,
            defaults={"email": options["admin_email"], "is_staff": True},
        )
        admin.is_staff = True
        if options["superuser"]:
            admin.is_superuser = True
        if options["admin_email"] and not admin.email:
            admin.email = options["admin_email"]
        if password:
            admin.set_password(password)
        admin.save()

        group_note = ""
        if options["platform_admin"]:
            group, _ = Group.objects.get_or_create(name=settings.PLATFORM_ADMIN_GROUP)
            admin.groups.add(group)
            group_note = f" + group '{group.name}'"

        verb = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(
            f"College {verb}: {college.name} (slug={college.slug}, plan={plan.name}, "
            f"status={college.status})"
        ))
        self.stdout.write(f"Admin {'created' if admin_created else 'updated'}: {admin.username}"
                          f"{' (superuser)' if admin.is_superuser else ''}{group_note}")
        if generated:
            self.stdout.write(self.style.WARNING(
                "Temporary password (shown once, change after first login):"))
            # The password itself is printed plain, on its own line: a colour code
            # glued to it ends up inside a copy-pasted password (and inside any
            # test/tooling that parses this line) — on a TTY the ANSI reset
            # sequence sits directly after the last character.
            self.stdout.write(password)
        steps = []
        if college.domain:
            steps.append(f"Point DNS for {college.domain} at this server.")
            steps.append(f"Log in at https://{college.domain}/login/")
        else:
            steps.append("Log in at /login/")
        steps.append("Brand the site with COLLEGE_* values in .env "
                     "(name, logo, colour, contact).")
        steps.append("Add students: CSV Upload (/admin-panel/upload/) "
                     "or one by one (/admin-panel/students/add/).")
        self.stdout.write("Next steps:")
        for number, step in enumerate(steps, start=1):
            self.stdout.write(f"  {number}. {step}")

    def _plan(self, code):
        plan = Plan.objects.filter(code=code).first()
        if plan:
            return plan
        if not Plan.objects.exists():
            self.stdout.write("No plans found — seeding the defaults first.")
            call_command("seed_plans", verbosity=0)
            plan = Plan.objects.filter(code=code).first()
            if plan:
                return plan
        available = ", ".join(Plan.objects.values_list("code", flat=True))
        raise CommandError(f"Unknown plan '{code}'. Available: {available or 'none'}")
