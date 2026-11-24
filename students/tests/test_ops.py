from django.test import TestCase, override_settings

from students.models import WebsiteVisit


class HealthzTests(TestCase):
    def test_healthz_returns_ok_json(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("environment", payload)

    def test_healthz_is_not_logged_as_a_visit(self):
        before = WebsiteVisit.objects.count()
        self.client.get("/healthz/")
        self.assertEqual(WebsiteVisit.objects.count(), before)

    def test_other_pages_are_still_logged(self):
        before = WebsiteVisit.objects.count()
        self.client.get("/login/")
        self.assertEqual(WebsiteVisit.objects.count(), before + 1)


class BrandingContextTests(TestCase):
    def test_login_page_uses_env_branding(self):
        with override_settings(
            COLLEGE_NAME="Test Institute of Technology",
            PRIMARY_COLOR="#123456",
            COLLEGE_LOGO="images/college_logo.jpg",
        ):
            html = self.client.get("/login/").content.decode()

        self.assertIn("Test Institute of Technology", html)
        self.assertIn("--highlight: #123456", html)
        self.assertIn("college-logo", html)

    def test_logo_falls_back_when_unset(self):
        with override_settings(COLLEGE_LOGO=""):
            html = self.client.get("/login/").content.decode()

        self.assertIn("college-logo-fallback", html)
        self.assertNotIn("college_logo.jpg", html)


class CleanStartTests(TestCase):
    """Things a fresh clone must get right without anyone remembering them."""

    def test_shell_scripts_are_executable_in_git(self):
        """The README says ./scripts/x.sh — that fails if git stores mode 100644."""
        import subprocess

        out = subprocess.run(['git', 'ls-files', '-s', '*.sh'], capture_output=True,
                             text=True, check=True).stdout
        non_exec = [line.split('\t')[1] for line in out.splitlines()
                    if line.startswith('100644')]
        self.assertEqual(non_exec, [], f"scripts committed without +x: {non_exec}")

    def test_env_example_has_no_inline_comments(self):
        """django-environ keeps '  # note' as part of the value -> startup crash."""
        from pathlib import Path

        from django.conf import settings

        path = Path(settings.BASE_DIR) / '.env.example'
        offenders = []
        for line in path.read_text().splitlines():
            if '=' not in line or line.strip().startswith('#'):
                continue
            key, value = line.split('=', 1)
            # a colour value legitimately starts with '#'; a comment is ' #'
            if ' #' in value or '\t#' in value:
                offenders.append(line)
        self.assertEqual(offenders, [], f"inline comments in .env.example: {offenders}")

    def test_tests_do_not_need_a_static_manifest(self):
        from django.conf import settings

        backend = settings.STORAGES['staticfiles']['BACKEND']
        self.assertIn('StaticFilesStorage', backend)
        self.assertNotIn('Manifest', backend)  # manifest is a build output, not a test input

    def test_create_college_command_exists(self):
        from django.core.management import get_commands

        self.assertIn('create_college', get_commands())
