"""Smoke test: every GET route of each role must render without a 500.

Catches broken imports/templates that unit tests miss (e.g. lazy imports inside
view functions and new shell markup).
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from students.models import FacultyProfile, StudentProfile, Subject

ADMIN_URLS = [
    "admin_dashboard", "csv_upload", "upload_history", "teacher_list",
    "teacher_create", "admin_list", "admin_create", "student_list",
    "export_students_csv", "export_set_password_links_csv", "notice_list",
    "notice_create", "subject_list", "subject_create", "marks_entry",
    "results_view", "attendance_entry", "take_attendance_bulk",
    "fee_structure_list", "fee_structure_create", "fee_payments",
    "fee_payment_create", "exam_schedule_list", "exam_schedule_create",
    "leave_applications", "event_list", "event_create", "feedback_report",
    "reports_view", "banner_upload", "doubt_list",
]

TEACHER_URLS = [
    "teacher_dashboard", "teacher_students", "teacher_take_attendance",
    "teacher_marks", "teacher_assignments", "teacher_materials",
    "teacher_schedule", "teacher_notices", "banner_upload", "doubt_list",
]

STUDENT_URLS = [
    "student_dashboard", "student_profile_edit", "student_fees",
    "student_exam_schedule", "student_leave_apply", "student_feedback",
    "student_events", "student_certificates", "change_password", "doubt_list",
]

PUBLIC_URLS = ["student_login", "healthz"]


class PageSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="smoke_admin", password="TestPass!2345", is_staff=True
        )
        cls.teacher_user = User.objects.create_user(
            username="smoke_teacher", password="TestPass!2345", is_staff=True
        )
        faculty = FacultyProfile.objects.create(user=cls.teacher_user, name="Smoke Teacher")
        subject = Subject.objects.create(
            branch="CS", semester=1, subject_code="SMK101", subject_name="Smoke Subject"
        )
        faculty.subjects.add(subject)

        cls.student_user = User.objects.create_user(
            username="smoke_student", password="TestPass!2345"
        )
        StudentProfile.objects.create(
            user=cls.student_user,
            name="Smoke Student",
            phone="9000000000",
            registration_number="SMK001",
            branch="CS",
            semester=1,
            is_password_changed=True,
        )

    def _check(self, names):
        for name in names:
            with self.subTest(view=name):
                response = self.client.get(reverse(name))
                self.assertLess(
                    response.status_code, 500,
                    f"{name} returned {response.status_code}",
                )

    def test_admin_pages_render(self):
        self.client.force_login(self.admin)
        self._check(ADMIN_URLS)

    def test_teacher_pages_render(self):
        self.client.force_login(self.teacher_user)
        self._check(TEACHER_URLS)

    def test_student_pages_render(self):
        self.client.force_login(self.student_user)
        self._check(STUDENT_URLS)

    def test_public_pages_render(self):
        self._check(PUBLIC_URLS)
