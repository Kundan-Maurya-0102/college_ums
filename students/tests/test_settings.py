import os

from django.conf import settings
from django.test import SimpleTestCase


class SettingsHardeningTests(SimpleTestCase):
    """The insecure defaults we removed must not come back."""

    def test_secret_key_is_real(self):
        self.assertTrue(settings.SECRET_KEY)
        self.assertNotEqual(settings.SECRET_KEY, "django-insecure-fallback-key")
        self.assertGreaterEqual(len(settings.SECRET_KEY), 20)

    def test_allowed_hosts_is_not_wildcard(self):
        self.assertNotIn("*", settings.ALLOWED_HOSTS)
        self.assertTrue(settings.ALLOWED_HOSTS)

    def test_token_timeout_comes_from_env(self):
        hours = int(os.environ.get("PASSWORD_TOKEN_TIMEOUT_HOURS", 48))
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, hours * 60 * 60)

    def test_csv_upload_limit_is_configured(self):
        self.assertIsInstance(settings.CSV_MAX_UPLOAD_MB, int)
        self.assertGreater(settings.CSV_MAX_UPLOAD_MB, 0)
