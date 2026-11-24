"""Data-protection feature tests: legal pages, redaction, export, erasure, retention."""
import io
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from students.models import AuditLog, Doubt, FeePayment, FeeStructure, StudentProfile
from students.privacy import anonymize_student, redact_mapping, redact_text, scrub_sentry_event


def make_student(username="priv_student", regno="PR001", **extra):
    user = User.objects.create_user(username=username, password="TestPass!2345")
    profile = StudentProfile.objects.create(
        user=user, name="Privacy Student", phone="9876543210",
        registration_number=regno, branch="CS", semester=1, **extra)
    return user, profile


class LegalPageTests(TestCase):
    def test_privacy_policy_is_public_and_branded(self):
        response = self.client.get(reverse("privacy_policy"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Privacy Policy")
        self.assertContains(response, "years")  # retention text uses DATA_RETENTION_YEARS

    def test_terms_page_is_public(self):
        response = self.client.get(reverse("terms_of_use"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Terms of Use")

    def test_login_page_links_to_legal_pages(self):
        body = self.client.get(reverse("student_login")).content.decode()
        self.assertIn(reverse("privacy_policy"), body)
        self.assertIn(reverse("terms_of_use"), body)

    @override_settings(DATA_RETENTION_YEARS=9)
    def test_retention_years_comes_from_settings(self):
        response = self.client.get(reverse("privacy_policy"))
        self.assertContains(response, "9")


class RedactionUnitTests(TestCase):
    def test_phone_email_and_ids_are_masked(self):
        text = redact_text("call 9876543210 or mail ram@example.com aadhaar 123412341234")
        self.assertNotIn("9876543210", text)
        self.assertNotIn("ram@example.com", text)
        self.assertNotIn("123412341234", text)
        self.assertIn("[phone]", text)
        self.assertIn("[email]", text)
        self.assertIn("[number]", text)

    def test_tokens_and_reset_links_are_masked(self):
        text = redact_text("url /set-password/Mw/abc123token/ and token abcdefghijklmnopqrst")
        self.assertNotIn("abc123token", text)
        self.assertNotIn("abcdefghijklmnopqrst", text)

    def test_mapping_redacts_sensitive_keys_only(self):
        cleaned = redact_mapping({"phone": "9876543210", "branch": "CS", "name": "Ram"})
        self.assertEqual(cleaned["phone"], "[redacted]")
        self.assertEqual(cleaned["branch"], "CS")
        self.assertEqual(cleaned["name"], "Ram")

    def test_sentry_event_scrubbing(self):
        event = {
            "user": {"email": "ram@example.com"},
            "request": {"data": {"phone": "9876543210"}, "cookies": {"sessionid": "secret"}},
            "exception": {"values": [{"value": "failed for 9876543210"}]},
        }
        cleaned = scrub_sentry_event(event)
        self.assertNotIn("user", cleaned)
        self.assertEqual(cleaned["request"]["cookies"], "[redacted]")
        self.assertEqual(cleaned["request"]["data"]["phone"], "[redacted]")
        self.assertNotIn("9876543210", cleaned["exception"]["values"][0]["value"])

    def test_logging_filter_redacts_record(self):
        import logging

        from students.logging_filters import RedactSensitiveFilter

        record = logging.LogRecord(
            "test", logging.INFO, __file__, 1,
            "student 9876543210 (ram@example.com) failed", None, None)
        RedactSensitiveFilter().filter(record)
        message = record.getMessage()
        self.assertNotIn("9876543210", message)
        self.assertNotIn("ram@example.com", message)


class ConsentTests(TestCase):
    def test_first_login_records_consent_time(self):
        user, profile = make_student()
        self.assertIsNone(profile.consent_given_at)
        response = self.client.post(reverse("student_login"),
                                    {"username": "priv_student", "password": "TestPass!2345"})
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        self.assertIsNotNone(profile.consent_given_at)

    def test_second_login_does_not_overwrite_consent_time(self):
        user, profile = make_student()
        original = timezone.now() - timedelta(days=10)
        StudentProfile.objects.filter(pk=profile.pk).update(consent_given_at=original)
        self.client.post(reverse("student_login"),
                         {"username": "priv_student", "password": "TestPass!2345"})
        profile.refresh_from_db()
        self.assertLess((profile.consent_given_at - original).total_seconds(), 5)


class StudentDataExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("exp_admin", password="TestPass!2345", is_staff=True)
        cls.student_user, cls.profile = make_student()
        cls.other_user = User.objects.create_user("exp_other", password="TestPass!2345")
        fee = FeeStructure.objects.create(branch="CS", semester=1, fee_type="TUITION",
                                          amount=5000, academic_year="2029-2030")
        FeePayment.objects.create(student=cls.profile, fee_structure=fee, amount_paid=5000,
                                  payment_date="2030-01-01", receipt_number="EXP-1", status="PAID")
        Doubt.objects.create(student=cls.profile, title="My doubt", content="help")

    def test_admin_can_export_and_audit_entry_written(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("student_data_export", args=[self.profile.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "no-store")

        payload = json.loads(response.content)
        self.assertEqual(payload["profile"]["registration_number"], "PR001")
        self.assertEqual(len(payload["fee_payments"]), 1)
        self.assertEqual(payload["doubts"][0]["title"], "My doubt")

        entry = AuditLog.objects.filter(action="student.data_export").first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.object_id, str(self.profile.pk))

    def test_export_does_not_include_password_hash(self):
        self.client.force_login(self.admin)
        body = self.client.get(reverse("student_data_export", args=[self.profile.pk])).content.decode()
        self.assertNotIn("pbkdf2", body)
        self.assertNotIn("password", body.lower())

    def test_non_admin_cannot_export(self):
        for user in (self.student_user, self.other_user):
            self.client.force_login(user)
            response = self.client.get(reverse("student_data_export", args=[self.profile.pk]))
            self.assertIn(response.status_code, (302, 403))


class StudentAnonymizeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("anon_admin", password="TestPass!2345", is_staff=True)
        cls.student_user, cls.profile = make_student("anon_student", "AN001")

    def test_confirm_page_lists_what_is_removed(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("student_anonymize", args=[self.profile.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Erase personal data")
        self.assertContains(response, "Registration number")

    def test_requires_confirmation_checkbox(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("student_anonymize", args=[self.profile.pk]), {})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, "Privacy Student")

    def test_anonymize_erases_pii_keeps_records_and_audits(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("student_anonymize", args=[self.profile.pk]),
                                    {"confirm": "yes"})
        self.assertEqual(response.status_code, 302)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, "Anonymised Student")
        self.assertEqual(self.profile.phone, "")
        self.assertEqual(self.profile.email, "")
        self.assertEqual(self.profile.registration_number, "AN001")  # kept for academics

        user = self.profile.user
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.username, f"anonymised-{self.profile.pk}")

        self.assertTrue(AuditLog.objects.filter(action="student.anonymize").exists())

    def test_anonymized_student_cannot_log_in(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("student_anonymize", args=[self.profile.pk]), {"confirm": "yes"})
        self.client.logout()
        response = self.client.post(reverse("student_login"),
                                    {"username": "anon_student", "password": "TestPass!2345"})
        self.assertEqual(response.status_code, 200)  # stays on login page
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_non_admin_cannot_anonymize(self):
        self.client.force_login(self.student_user)
        self.client.post(reverse("student_anonymize", args=[self.profile.pk]), {"confirm": "yes"})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, "Privacy Student")


class RetentionCommandTests(TestCase):
    def setUp(self):
        self.old_user, self.old_profile = make_student("old_student", "OLD001", year_of_admission=2001)
        self.new_user, self.new_profile = make_student("new_student", "NEW001",
                                                       year_of_admission=timezone.now().year)

    @override_settings(DATA_RETENTION_YEARS=5)
    def test_dry_run_changes_nothing(self):
        out = io.StringIO()
        call_command("purge_expired_data", stdout=out)
        self.old_profile.refresh_from_db()
        self.assertEqual(self.old_profile.name, "Privacy Student")
        self.assertIn("Dry run", out.getvalue())

    @override_settings(DATA_RETENTION_YEARS=5)
    def test_apply_anonymizes_only_expired_students(self):
        call_command("purge_expired_data", "--apply", stdout=io.StringIO())
        self.old_profile.refresh_from_db()
        self.new_profile.refresh_from_db()
        self.assertEqual(self.old_profile.name, "Anonymised Student")
        self.assertEqual(self.new_profile.name, "Privacy Student")
        self.assertTrue(AuditLog.objects.filter(action="retention.anonymize").exists())

    @override_settings(AUDIT_LOG_RETENTION_DAYS=30, VISIT_RETENTION_DAYS=30)
    def test_apply_prunes_old_logs(self):
        entry = AuditLog.objects.create(action="old.entry")
        AuditLog.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=90))
        call_command("purge_expired_data", "--apply", "--years", "999",
                     stdout=io.StringIO())
        self.assertFalse(AuditLog.objects.filter(pk=entry.pk).exists())

    def test_anonymize_helper_is_idempotent(self):
        anonymize_student(self.old_profile)
        anonymize_student(self.old_profile)
        self.old_profile.refresh_from_db()
        self.assertEqual(self.old_profile.name, "Anonymised Student")
