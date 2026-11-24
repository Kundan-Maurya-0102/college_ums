"""`manage.py create_college` must turn a fresh install into a usable college."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from platform_admin.models import College, Plan

User = get_user_model()


class CreateCollegeCommandTests(TestCase):
    def run_command(self, *args, **kwargs):
        out = StringIO()
        call_command("create_college", *args, stdout=out, stderr=out, **kwargs)
        return out.getvalue()

    def test_creates_plan_college_and_admin(self):
        output = self.run_command(
            "--name", "Govt Polytechnic Gaya", "--slug", "gpgaya",
            "--domain", "ums.gpgaya.ac.in", "--plan", "pro",
            "--admin-username", "principal", "--admin-password", "Str0ng@12345",
        )
        college = College.objects.get(slug="gpgaya")
        self.assertEqual(college.name, "Govt Polytechnic Gaya")
        self.assertEqual(college.domain, "ums.gpgaya.ac.in")
        self.assertEqual(college.plan.code, "pro")
        self.assertEqual(college.status, College.STATUS_TRIAL)

        admin = User.objects.get(username="principal")
        self.assertTrue(admin.is_staff)
        self.assertFalse(admin.is_superuser)          # least privilege by default
        self.assertTrue(admin.check_password("Str0ng@12345"))
        self.assertIn("ums.gpgaya.ac.in", output)

    def test_admin_joins_the_platform_group(self):
        self.run_command("--name", "A College", "--slug", "acollege",
                         "--admin-username", "padmin", "--admin-password", "Str0ng@12345")
        group = Group.objects.get(name="Platform Admin")
        self.assertTrue(User.objects.get(username="padmin").groups.filter(pk=group.pk).exists())

    def test_superuser_flag_is_opt_in(self):
        self.run_command("--name", "B College", "--slug", "bcollege", "--superuser",
                         "--admin-username", "boss", "--admin-password", "Str0ng@12345")
        self.assertTrue(User.objects.get(username="boss").is_superuser)

    def test_generated_password_is_printed_and_works(self):
        output = self.run_command("--name", "C College", "--slug", "ccollege",
                                  "--admin-username", "cadmin")
        self.assertIn("Temporary password", output)
        password = output.split("Temporary password (shown once, change after first login): ")[1].split()[0]
        self.assertTrue(User.objects.get(username="cadmin").check_password(password))

    def test_existing_slug_is_an_error_without_update(self):
        self.run_command("--name", "D College", "--slug", "dcollege",
                         "--admin-username", "dadmin", "--admin-password", "Str0ng@12345")
        with self.assertRaises(CommandError):
            self.run_command("--name", "D College", "--slug", "dcollege",
                             "--admin-username", "dadmin2")

    def test_update_changes_plan_and_domain(self):
        self.run_command("--name", "E College", "--slug", "ecollege", "--plan", "basic",
                         "--admin-username", "eadmin", "--admin-password", "Str0ng@12345")
        self.run_command("--name", "E College", "--slug", "ecollege", "--plan", "enterprise",
                         "--domain", "ums.e.edu", "--update",
                         "--admin-username", "eadmin")
        college = College.objects.get(slug="ecollege")
        self.assertEqual(college.plan.code, "enterprise")
        self.assertEqual(college.domain, "ums.e.edu")

    def test_active_when_no_trial(self):
        self.run_command("--name", "F College", "--slug", "fcollege", "--trial-days", "0",
                         "--admin-username", "fadmin", "--admin-password", "Str0ng@12345")
        college = College.objects.get(slug="fcollege")
        self.assertEqual(college.status, College.STATUS_ACTIVE)
        self.assertIsNone(college.subscription_expires_on)

    def test_dry_run_writes_nothing(self):
        self.run_command("--name", "G College", "--slug", "gcollege", "--dry-run",
                         "--admin-username", "gadmin")
        self.assertFalse(College.objects.filter(slug="gcollege").exists())
        self.assertFalse(User.objects.filter(username="gadmin").exists())

    def test_unknown_plan_lists_the_available_codes(self):
        Plan.objects.all().delete()
        with self.assertRaises(CommandError) as ctx:
            self.run_command("--name", "H College", "--slug", "hcollege", "--plan", "nope",
                             "--admin-username", "hadmin")
        self.assertIn("Available", str(ctx.exception))

    def test_slug_is_derived_from_the_name(self):
        self.run_command("--name", "Shri Ram Polytechnic Ara", "--admin-username", "ramadmin",
                         "--admin-password", "Str0ng@12345")
        self.assertTrue(College.objects.filter(slug="shri-ram-polytechnic-ara").exists())


@override_settings(DEBUG=False)
class SecretKeyGuardTests(TestCase):
    """A placeholder key from .env.example must not survive into production."""

    def _settings_with(self, secret_key, debug=False):
        import importlib
        import os

        from django.conf import settings

        old = os.environ.get("SECRET_KEY")
        os.environ["SECRET_KEY"] = secret_key
        os.environ["DEBUG"] = "False"
        try:
            import sys

            for module in [m for m in sys.modules if m.startswith("college_ums")]:
                del sys.modules[module]
            module = importlib.import_module("college_ums.settings")
            return module
        finally:
            if old is None:
                os.environ.pop("SECRET_KEY", None)
            else:
                os.environ["SECRET_KEY"] = old
            os.environ.pop("DEBUG", None)
            settings.SECRET_KEY = settings.SECRET_KEY  # no-op, keep linters quiet

    def test_placeholder_key_is_rejected(self):
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaises(ImproperlyConfigured):
            self._settings_with("replace-with-a-random-50-plus-character-key")

    def test_django_insecure_key_is_rejected(self):
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaises(ImproperlyConfigured):
            self._settings_with("django-insecure-abcdefghijklmnopqrstuvwxyz0123456789")

    def test_short_key_is_rejected(self):
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaises(ImproperlyConfigured):
            self._settings_with("too-short")

    def test_long_random_key_is_accepted(self):
        module = self._settings_with("Zx9" * 20)
        self.assertEqual(module.DEBUG, False)
