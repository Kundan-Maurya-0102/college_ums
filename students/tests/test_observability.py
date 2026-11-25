"""Health/readiness probes, structured logging and error-tracking wiring."""
import json
import logging
from unittest.mock import patch

from django.test import TestCase


class HealthProbeTests(TestCase):
    def test_healthz_is_db_free_and_reports_environment(self):
        response = self.client.get("/healthz/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("environment", payload)

    def test_healthz_works_even_when_the_database_is_down(self):
        with patch("django.db.backends.utils.CursorWrapper.execute",
                   side_effect=RuntimeError("db down")):
            response = self.client.get("/healthz/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)

    def test_readyz_reports_db_and_cache(self):
        response = self.client.get("/readyz/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["db"])
        self.assertTrue(payload["cache"])

    def test_readyz_returns_503_when_the_database_fails(self):
        with patch("django.db.connection.cursor", side_effect=RuntimeError("db gone")):
            response = self.client.get("/readyz/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertFalse(payload["db"])
        self.assertEqual(payload["status"], "degraded")
        self.assertIn("db_error", payload["errors"])

    def test_readyz_returns_503_when_cache_fails(self):
        with patch("django.core.cache.cache.set", side_effect=RuntimeError("cache gone")):
            response = self.client.get("/readyz/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["cache"])

    def test_probes_are_not_visit_logged(self):
        from students.models import WebsiteVisit

        before = WebsiteVisit.objects.count()
        self.client.get("/healthz/", HTTP_HOST="localhost")
        self.client.get("/readyz/", HTTP_HOST="localhost")
        self.assertEqual(WebsiteVisit.objects.count(), before)


class StructuredLoggingTests(TestCase):
    def test_json_formatter_emits_one_object_with_fields(self):
        from students.log_formatter import JsonFormatter

        record = logging.LogRecord("students.test", logging.WARNING, "x.py", 10,
                                   "student %s failed", ("9876543210",), None)
        record.environment = "staging"
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload["level"], "WARNING")
        self.assertEqual(payload["logger"], "students.test")
        self.assertEqual(payload["environment"], "staging")
        self.assertEqual(payload["msg"], "student 9876543210 failed")

    def test_redaction_filter_runs_before_formatting(self):
        from students.log_formatter import JsonFormatter
        from students.logging_filters import RedactSensitiveFilter

        record = logging.LogRecord("students.test", logging.ERROR, "x.py", 1,
                                   "mail rahul@example.com phone 9876543210", (), None)
        RedactSensitiveFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
        self.assertNotIn("rahul@example.com", payload["msg"])
        self.assertNotIn("9876543210", payload["msg"])
        self.assertIn("[email]", payload["msg"])

    def test_context_filter_sets_environment(self):
        from students.log_formatter import ContextFilter

        record = logging.LogRecord("x", logging.INFO, "f", 1, "m", (), None)
        ContextFilter("production").filter(record)
        self.assertEqual(record.environment, "production")


class SentryWiringTests(TestCase):
    def test_scrub_hooks_are_callable_and_redact(self):
        from students.privacy import scrub_breadcrumb, scrub_sentry_event

        event = {
            "message": "student 9876543210 rahul@example.com",
            "request": {"data": "password=hunter2", "cookies": {"sessionid": "abc"}},
            "extra": {"phone": "9876543210"},
        }
        scrubbed = scrub_sentry_event(event, {})
        flat = json.dumps(scrubbed, default=str)
        self.assertNotIn("9876543210", flat)
        self.assertNotIn("rahul@example.com", flat)

        breadcrumb = scrub_breadcrumb({"message": "call 9876543210"}, {})
        self.assertNotIn("9876543210", json.dumps(breadcrumb, default=str))

    def test_sentry_sdk_accepts_our_configuration(self):
        try:
            import sentry_sdk
        except ImportError:  # optional dependency
            self.skipTest("sentry-sdk not installed")
        from sentry_sdk.integrations.django import DjangoIntegration

        from students.privacy import scrub_breadcrumb, scrub_sentry_event

        # The SDK is global: restore the "no DSN" state afterwards, otherwise the rest
        # of the suite keeps trying to reach example.invalid and slows down.
        self.addCleanup(sentry_sdk.init, dsn="")
        client = sentry_sdk.init(
            dsn="https://public@example.invalid/1",
            integrations=[DjangoIntegration()],
            send_default_pii=False,
            before_send=scrub_sentry_event,
            before_breadcrumb=scrub_breadcrumb,
            max_request_body_size="never",
            environment="test",
        )
        self.assertIsNotNone(client)
