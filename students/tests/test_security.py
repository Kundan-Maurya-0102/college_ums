"""Security regression tests: permissions, IDOR, throttling, headers, uploads."""
import datetime

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from students.forms import AssignmentForm, BannerImageForm
from students.models import (Assignment, AuditLog, Doubt, DoubtReply, FacultyProfile,
                             FeePayment, FeeStructure, StudentProfile, Subject)
from students.security import safe_upload_name, validate_upload

ADMIN_ONLY = [
    "admin_dashboard", "teacher_list", "teacher_create", "admin_list",
    "admin_create", "student_list", "export_students_csv",
    "export_set_password_links_csv", "csv_upload", "upload_history",
    "notice_list", "notice_create", "subject_list", "marks_entry",
    "results_view", "attendance_entry", "exam_schedule_list",
    "fee_structure_list", "fee_payments", "fee_payment_create",
    "leave_applications", "event_list", "feedback_report", "reports_view",
]

TEACHER_ONLY = [
    "teacher_dashboard", "teacher_students", "teacher_take_attendance",
    "teacher_marks", "teacher_assignments", "teacher_materials",
    "teacher_schedule", "teacher_notices",
]

SHARED_AUTHENTICATED = ["change_password", "doubt_list"]

STUDENT_ONLY = [
    "student_dashboard", "student_fees", "student_exam_schedule",
    "student_leave_apply", "student_feedback", "student_events",
    "student_certificates", "student_profile_edit",
]


def make_student(username, regno, **extra):
    user = User.objects.create_user(username=username, password="TestPass!2345")
    profile = StudentProfile.objects.create(
        user=user, name=extra.pop("name", username.title()), phone="9876543210",
        registration_number=regno, branch="CS", semester=1,
        is_password_changed=True, **extra)
    return user, profile


class PermissionMatrixTests(TestCase):
    """Role x page matrix: see docs/PERMISSIONS.md."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("matrix_admin", password="TestPass!2345", is_staff=True)
        cls.teacher_user = User.objects.create_user("matrix_teacher", password="TestPass!2345", is_staff=True)
        faculty = FacultyProfile.objects.create(user=cls.teacher_user, name="Matrix Teacher")
        cls.subject = Subject.objects.create(branch="CS", semester=1, subject_code="MX101", subject_name="Matrix")
        faculty.subjects.add(cls.subject)
        cls.student_user, cls.student = make_student("matrix_student", "MX001")

    def _denied(self, names, user):
        self.client.force_login(user)
        allowed = []
        for name in names:
            response = self.client.get(reverse(name))
            if response.status_code == 200:
                allowed.append(name)
        return allowed

    def test_student_cannot_reach_admin_pages(self):
        self.assertEqual(self._denied(ADMIN_ONLY, self.student_user), [])

    def test_teacher_cannot_reach_admin_pages(self):
        self.assertEqual(self._denied(ADMIN_ONLY, self.teacher_user), [])

    def test_student_cannot_reach_teacher_pages(self):
        self.assertEqual(self._denied(TEACHER_ONLY, self.student_user), [])

    def test_teacher_cannot_reach_student_portal(self):
        self.assertEqual(self._denied(STUDENT_ONLY, self.teacher_user), [])

    def test_admin_cannot_reach_student_portal(self):
        self.assertEqual(self._denied(STUDENT_ONLY, self.admin), [])

    def test_anonymous_blocked_everywhere(self):
        blocked = 0
        for name in ADMIN_ONLY + TEACHER_ONLY + STUDENT_ONLY + SHARED_AUTHENTICATED:
            response = self.client.get(reverse(name))
            self.assertIn(response.status_code, (302, 403), f"{name} open to anonymous users")
            blocked += 1
        self.assertEqual(blocked, len(ADMIN_ONLY + TEACHER_ONLY + STUDENT_ONLY + SHARED_AUTHENTICATED))


class IDORTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student_a_user, cls.student_a = make_student("idor_a", "IDA001")
        cls.student_b_user, cls.student_b = make_student("idor_b", "IDB001")
        cls.fee = FeeStructure.objects.create(branch="CS", semester=1, fee_type="TUITION",
                                              amount=5000, academic_year="2029-2030")
        cls.doubt_a = Doubt.objects.create(student=cls.student_a, title="A doubt", content="mine")
        cls.reply_a = DoubtReply.objects.create(doubt=cls.doubt_a, user=cls.student_a_user, content="reply")
        cls.payment_b = FeePayment.objects.create(
            student=cls.student_b, amount_paid=5000, payment_date=datetime.date.today(),
            status="PAID", receipt_number="RCPT-B-1", fee_structure=cls.fee)

    def test_student_cannot_edit_another_students_doubt(self):
        self.client.force_login(self.student_b_user)
        response = self.client.get(reverse("doubt_edit", args=[self.doubt_a.pk]))
        self.assertEqual(response.status_code, 302)
        self.doubt_a.refresh_from_db()
        self.assertEqual(self.doubt_a.title, "A doubt")

    def test_student_cannot_delete_another_students_reply(self):
        self.client.force_login(self.student_b_user)
        response = self.client.post(reverse("reply_delete", args=[self.reply_a.pk]))
        self.assertIn(response.status_code, (302, 403))
        self.assertTrue(DoubtReply.objects.filter(pk=self.reply_a.pk).exists())

    def test_student_fee_page_only_shows_own_payments(self):
        self.client.force_login(self.student_a_user)
        response = self.client.get(reverse("student_fees"))
        self.assertEqual(response.status_code, 200)
        payments = list(response.context["payments"])
        self.assertNotIn(self.payment_b, payments)

    def test_student_certificate_page_uses_own_profile(self):
        self.client.force_login(self.student_a_user)
        response = self.client.get(reverse("student_certificates"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["profile"], self.student_a)


class LoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user, self.profile = make_student("throttle_student", "TH001")

    def tearDown(self):
        cache.clear()

    def _post(self, password, ip="10.0.0.1"):
        return self.client.post(reverse("student_login"),
                                {"username": "throttle_student", "password": password},
                                REMOTE_ADDR=ip)

    @override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_LOCKOUT_SECONDS=900)
    def test_lockout_after_repeated_failures(self):
        for _ in range(3):
            self._post("wrong-password")
        response = self._post("TestPass!2345")
        self.assertEqual(response.status_code, 200)  # still on the login page
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "Too many failed login attempts")

    @override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_LOCKOUT_SECONDS=900)
    def test_successful_login_resets_counter(self):
        self._post("wrong-password")
        self._post("wrong-password")
        ok = self._post("TestPass!2345")
        self.assertEqual(ok.status_code, 302)
        cache.clear()
        self.client.logout()
        again = self._post("TestPass!2345")
        self.assertEqual(again.status_code, 302)

    @override_settings(LOGIN_MAX_ATTEMPTS=2, LOGIN_LOCKOUT_SECONDS=900)
    def test_other_ip_is_not_locked(self):
        self._post("bad", ip="10.0.0.9")
        self._post("bad", ip="10.0.0.9")
        response = self._post("TestPass!2345", ip="10.0.0.10")
        self.assertEqual(response.status_code, 302)


class SecurityHeaderTests(TestCase):
    def test_headers_present_on_login_page(self):
        response = self.client.get(reverse("student_login"))
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("geolocation=()", response["Permissions-Policy"])


class UploadValidationTests(TestCase):
    def test_executable_extension_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_upload(SimpleUploadedFile("evil.exe", b"MZ"), {"pdf"})

    def test_html_and_svg_are_rejected(self):
        for name in ("xss.html", "logo.svg"):
            with self.assertRaises(ValidationError):
                validate_upload(SimpleUploadedFile(name, b"<script>"), {"html", "svg"})

    def test_wrong_extension_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_upload(SimpleUploadedFile("notes.exe", b"x"), {"pdf"})

    def test_oversize_is_rejected(self):
        with override_settings(CSV_MAX_UPLOAD_MB=1):
            blob = SimpleUploadedFile("big.pdf", b"0" * (2 * 1024 * 1024))
            with self.assertRaises(ValidationError):
                validate_upload(blob, {"pdf"}, max_mb=1)

    def test_file_name_is_sanitised(self):
        upload = SimpleUploadedFile("../../etc/pass wd<script>.pdf", b"data")
        validate_upload(upload, {"pdf"})
        self.assertNotIn("/", upload.name)
        self.assertNotIn("<", upload.name)
        self.assertTrue(upload.name.endswith(".pdf"))

    def test_safe_upload_name_handles_windows_paths(self):
        self.assertEqual(safe_upload_name("C:\\temp\\my file.PDF"), "my-file.pdf")

    def test_assignment_form_rejects_executable(self):
        form = AssignmentForm(data={"title": "x", "subject": self._subject().pk,
                                    "due_date": "2030-01-01", "is_active": "on"},
                              files={"attachment": SimpleUploadedFile("run.exe", b"MZ")})
        self.assertFalse(form.is_valid())
        self.assertIn("attachment", form.errors)

    def test_banner_form_rejects_non_image(self):
        form = BannerImageForm(data={"title": "x"},
                               files={"image": SimpleUploadedFile("fake.png", b"not an image")})
        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def _subject(self):
        return Subject.objects.create(branch="CS", semester=1, subject_code="UP101",
                                      subject_name="Uploads")


class AuditLogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("audit_admin", password="TestPass!2345", is_staff=True)
        cls.student_user, cls.student = make_student("audit_student", "AU001")
        cls.subject = Subject.objects.create(branch="CS", semester=1, subject_code="AU101",
                                             subject_name="Audit")
        cls.teacher_user = User.objects.create_user("audit_teacher", password="TestPass!2345", is_staff=True)
        FacultyProfile.objects.create(user=cls.teacher_user, name="Audit Teacher")
        cls.fee = FeeStructure.objects.create(branch="CS", semester=1, fee_type="TUITION",
                                              amount=5000, academic_year="2029-2030")

    def test_fee_payment_is_audited(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("fee_payment_create"), {
            "student": self.student.pk, "fee_structure": self.fee.pk,
            "amount_paid": "1000", "payment_date": "2030-01-01",
            "payment_mode": "CASH", "status": "PAID", "remarks": "",
            "receipt_number": "RCPT-A-1",
        })
        entry = AuditLog.objects.filter(action="fee.payment.create").first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.user, self.admin)
        self.assertEqual(entry.model_name, "FeePayment")

    def test_student_edit_is_audited(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("student_edit", args=[self.student.pk]), {
            "name": "Audit Student", "phone": "9876543210",
            "registration_number": "AU001", "branch": "CS", "semester": "1",
            "email": "", "admission_year": "", "father_name": "", "mother_name": "",
            "date_of_birth": "", "address": "",
        })
        self.assertTrue(AuditLog.objects.filter(action="student.update",
                                                object_id=str(self.student.pk)).exists())


class ChatbotApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student_user, cls.student = make_student("chat_student", "CH001")

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_empty_prompt_is_rejected_without_calling_ai(self):
        self.client.force_login(self.student_user)
        response = self.client.post(reverse("ai_chatbot_api"), data="{}",
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Please type a question.")

    def test_malformed_json_returns_400_not_500(self):
        self.client.force_login(self.student_user)
        response = self.client.post(reverse("ai_chatbot_api"), data="not-json",
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("JSON", response.json()["error"])

    def test_rate_limit_returns_429(self):
        self.client.force_login(self.student_user)
        for _ in range(20):
            self.client.post(reverse("ai_chatbot_api"), data="{}",
                             content_type="application/json")
        response = self.client.post(reverse("ai_chatbot_api"), data="{}",
                                    content_type="application/json")
        self.assertEqual(response.status_code, 429)

    def test_anonymous_cannot_use_chat_api(self):
        response = self.client.post(reverse("ai_chatbot_api"), data="{}",
                                    content_type="application/json")
        self.assertEqual(response.status_code, 302)


class BannerPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("banner_admin", password="TestPass!2345", is_staff=True)
        cls.student_user, cls.student = make_student("banner_student", "BN001")

    def test_student_cannot_open_banner_upload(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("banner_upload"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("student_dashboard"))

    def test_student_cannot_delete_banner(self):
        from students.models import BannerImage
        banner = BannerImage.objects.create(title="t", uploaded_by=self.admin)
        self.client.force_login(self.student_user)
        response = self.client.post(reverse("banner_delete", args=[banner.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(BannerImage.objects.filter(pk=banner.pk).exists())

    def test_admin_can_open_banner_upload(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("banner_upload")).status_code, 200)
