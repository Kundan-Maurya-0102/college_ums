"""Background job + graceful-degradation tests."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from students import tasks


class TaskQueueTests(TestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_task_sends(self):
        result = tasks.send_email_task("student@example.com", "Notice", "Hello")
        self.assertIn("sent", result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["student@example.com"])

    def test_email_task_skips_blank_address(self):
        self.assertIn("skipped", tasks.send_email_task("", "x", "y"))

    @override_settings(TWILIO_ACCOUNT_SID="", TWILIO_AUTH_TOKEN="")
    def test_whatsapp_without_credentials_is_skipped(self):
        self.assertIn("skipped", tasks.send_whatsapp_task("9876543210", "hi"))

    @override_settings(TWILIO_ACCOUNT_SID="AC123", TWILIO_AUTH_TOKEN="tok", TASK_MAX_ATTEMPTS=3)
    def test_whatsapp_network_error_is_retried_then_reported(self):
        with patch("students.tasks.time.sleep"), \
                patch("students.tasks._make_twilio_client") as client_cls:
            client_cls.return_value.messages.create.side_effect = Exception("connection reset")
            result = tasks.send_whatsapp_task("9876543210", "hi")
        self.assertEqual(client_cls.return_value.messages.create.call_count, 3)
        self.assertIn("failed", result)

    @override_settings(TWILIO_ACCOUNT_SID="AC123", TWILIO_AUTH_TOKEN="tok")
    def test_whatsapp_permanent_error_is_not_retried(self):
        with patch("students.tasks.time.sleep"), \
                patch("students.tasks._make_twilio_client") as client_cls:
            client_cls.return_value.messages.create.side_effect = Exception("invalid number")
            result = tasks.send_whatsapp_task("bad", "hi")
        self.assertEqual(client_cls.return_value.messages.create.call_count, 1)
        self.assertIn("failed", result)

    @override_settings(TWILIO_ACCOUNT_SID="AC123", TWILIO_AUTH_TOKEN="tok")
    def test_whatsapp_succeeds_after_transient_failure(self):
        calls = {"n": 0}

        def flaky(**kwargs):
            calls["n"] += 1
            if calls["n"] < 2:
                raise Exception("502 bad gateway")
            return type("Msg", (), {"sid": "SM123"})()

        with patch("students.tasks.time.sleep"), \
                patch("students.tasks._make_twilio_client") as client_cls:
            client_cls.return_value.messages.create.side_effect = flaky
            result = tasks.send_whatsapp_task("9876543210", "hi")
        self.assertIn("sent (SM123)", result)
        self.assertEqual(calls["n"], 2)

    def test_with_retries_gives_up_after_limit(self):
        calls = {"n": 0}

        def always_timeout():
            calls["n"] += 1
            raise TimeoutError("timed out")

        with patch("students.tasks.time.sleep"):
            with self.assertRaises(TimeoutError):
                tasks.with_retries(always_timeout, attempts=3)
        self.assertEqual(calls["n"], 3)

    def test_with_retries_does_not_retry_permanent_errors(self):
        calls = {"n": 0}

        def invalid_number():
            calls["n"] += 1
            raise ValueError("invalid number")

        with patch("students.tasks.time.sleep"):
            with self.assertRaises(ValueError):
                tasks.with_retries(invalid_number, attempts=3)
        self.assertEqual(calls["n"], 1)

    def test_enqueue_falls_back_when_broker_is_down(self):
        with patch("django_q.tasks.async_task", side_effect=RuntimeError("broker down")):
            with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
                status, detail = tasks.notify("email", "a@b.com", "Subject", "Body")
        self.assertEqual(status, "ran")
        self.assertIn("sent", detail)
        self.assertEqual(len(mail.outbox), 1)

    def test_enqueue_reports_queued_task_id(self):
        with patch("django_q.tasks.async_task", return_value="task-123"):
            status, detail = tasks.notify("whatsapp", "9876543210", "", "hello")
        self.assertEqual((status, detail), ("queued", "task-123"))

    def test_run_now_swallows_and_reports_failures(self):
        def boom():
            raise ValueError("nope")

        status, detail = tasks.run_now(boom)
        self.assertEqual(status, "failed")
        self.assertIn("nope", detail)

    def test_unknown_channel(self):
        status, _ = tasks.notify("pigeon", "x", "y", "z")
        self.assertEqual(status, "failed")

    def test_send_credentials_skips_deleted_student(self):
        self.assertEqual(tasks.send_credentials_task(999999), "skipped (student deleted)")


class GracefulImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("imp_admin", password="TestPass!2345", is_staff=True)

    def test_broken_importer_shows_message_instead_of_500(self):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile

        rows = b"name,registration_number,branch,semester\r\n" + b"".join(
            f"Student {i},IMP{i:03d},CS,1\r\n".encode() for i in range(1, 6))
        csv_file = SimpleUploadedFile("students.csv", rows, content_type="text/csv")
        self.client.force_login(self.admin)
        with patch("students.views.imports.process_any_csv_upload",
                   side_effect=RuntimeError("pandas exploded")):
            response = self.client.post(reverse("csv_upload"),
                                        {"upload_type": "STUDENTS", "description": "load test", "file": csv_file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import fail ho gaya")

    def test_error_page_hides_traceback(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("csv_upload"), {})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Traceback", response.content.decode())
