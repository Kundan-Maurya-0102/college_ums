from django.contrib.auth.models import User
from django.test import TestCase

from students.models import FacultyProfile, Notice, StudentProfile, Subject


def make_student(username="cs2024001", registration_number="CS2024001", **extra):
    user = User.objects.create_user(username=username, password="TestPass!2345")
    profile = StudentProfile.objects.create(
        user=user,
        name=extra.pop("name", "Asha Kumari"),
        phone="9876543210",
        registration_number=registration_number,
        branch="CS",
        semester=1,
        is_password_changed=True,
        **extra,
    )
    return user, profile


def make_teacher(username="teacher1", name="Ravi Sir"):
    user = User.objects.create_user(username=username, password="TestPass!2345", is_staff=True)
    faculty = FacultyProfile.objects.create(user=user, name=name)
    return user, faculty


class AnonymousAccessTests(TestCase):
    def test_protected_pages_redirect_to_login(self):
        for url in ["/dashboard/", "/admin-panel/", "/teacher/", "/my-fees/"]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login/", response["Location"])

    def test_healthz_is_public(self):
        self.assertEqual(self.client.get("/healthz/").status_code, 200)


class StudentAccessTests(TestCase):
    def setUp(self):
        self.user, self.profile = make_student()

    def test_student_gets_dashboard(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)

    def test_student_cannot_open_admin_panel(self):
        self.client.force_login(self.user)
        response = self.client.get("/admin-panel/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_student_cannot_open_teacher_panel(self):
        self.client.force_login(self.user)
        response = self.client.get("/teacher/")
        self.assertEqual(response.status_code, 302)

    def test_student_cannot_export_credentials(self):
        self.client.force_login(self.user)
        response = self.client.get("/admin-panel/credentials/export-links/")
        self.assertEqual(response.status_code, 302)


class TeacherAccessTests(TestCase):
    def setUp(self):
        self.user, self.faculty = make_teacher()
        self.subject = Subject.objects.create(
            branch="CS", semester=1, subject_code="CS101", subject_name="Programming"
        )
        self.faculty.subjects.add(self.subject)

    def test_teacher_gets_teacher_dashboard(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/teacher/").status_code, 200)

    def test_teacher_cannot_open_admin_panel(self):
        self.client.force_login(self.user)
        response = self.client.get("/admin-panel/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_teacher_cannot_open_admin_student_list(self):
        self.client.force_login(self.user)
        response = self.client.get("/admin-panel/students/")
        self.assertEqual(response.status_code, 302)

    def test_teacher_cannot_edit_another_teachers_notice(self):
        other_user, other_faculty = make_teacher(username="teacher2", name="Other Sir")
        notice = Notice.objects.create(title="Mine", content="x", created_by=other_faculty)

        self.client.force_login(self.user)
        response = self.client.get(f"/teacher/notices/{notice.pk}/edit/")
        self.assertEqual(response.status_code, 404)


class AdminAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="office_admin", password="TestPass!2345", is_staff=True
        )

    def test_staff_without_faculty_profile_is_admin(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/admin-panel/").status_code, 200)
        self.assertEqual(self.client.get("/admin-panel/upload/").status_code, 200)

    def test_inactive_teacher_is_not_treated_as_teacher(self):
        teacher_user, faculty = make_teacher()
        faculty.is_active = False
        faculty.save()

        self.client.force_login(teacher_user)
        response = self.client.get("/teacher/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])
