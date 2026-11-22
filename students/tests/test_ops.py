from django.test import TestCase, override_settings

from students.models import WebsiteVisit


class HealthzTests(TestCase):
    def test_healthz_returns_ok_json(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

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
