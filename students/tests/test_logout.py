"""Logout is a POST: a GET must never end the session."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from students.models import FacultyProfile, StudentProfile

User = get_user_model()


class LogoutMethodTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student_user = User.objects.create_user('lo-student', password='TestPass@12345')
        StudentProfile.objects.create(user=cls.student_user, name='Logout Student',
                                      registration_number='LO001', branch='CS', semester=3,
                                      year_of_admission=2023, is_password_changed=True)
        cls.admin = User.objects.create_user('lo-admin', password='TestPass@12345',
                                             is_staff=True, is_superuser=True)
        teacher_user = User.objects.create_user('lo-teacher', password='TestPass@12345',
                                                is_staff=True)
        FacultyProfile.objects.create(user=teacher_user, name='Logout Teacher', department='CS')
        cls.teacher_user = teacher_user

    def test_get_asks_for_confirmation_and_keeps_the_session(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.student_user)
        response = client.get(reverse('student_logout'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'student/logout_confirm.html')
        self.assertContains(response, 'csrfmiddlewaretoken')
        # still signed in
        self.assertEqual(client.get(reverse('student_dashboard')).status_code, 200)

    def test_post_logs_out_and_redirects_to_login(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.student_user)
        response = client.post(reverse('student_logout'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])
        self.assertEqual(client.get(reverse('student_dashboard')).status_code, 302)

    def test_post_without_csrf_token_is_refused(self):
        client = Client(HTTP_HOST='localhost', enforce_csrf_checks=True)
        client.force_login(self.student_user)
        response = client.post(reverse('student_logout'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(client.get(reverse('student_dashboard')).status_code, 200)

    def test_every_role_can_log_out_with_post(self):
        for user in (self.student_user, self.teacher_user, self.admin):
            with self.subTest(user=user.username):
                client = Client(HTTP_HOST='localhost')
                client.force_login(user)
                self.assertEqual(client.post(reverse('student_logout')).status_code, 302)
                self.assertEqual(client.get(reverse('home')).status_code, 200)

    def test_no_page_ships_a_get_logout_link(self):
        """Every logout control must be a form button, never an <a href>."""
        pages = {
            self.student_user: ['/dashboard/', '/notices/', '/attendance/', '/forum/'],
            self.teacher_user: ['/teacher/', '/teacher/students/', '/teacher/attendance/'],
            self.admin: ['/admin-panel/', '/admin-panel/students/', '/admin-panel/reports/'],
        }
        for user, urls in pages.items():
            client = Client(HTTP_HOST='localhost')
            client.force_login(user)
            for url in urls:
                with self.subTest(user=user.username, url=url):
                    body = client.get(url).content.decode()
                    self.assertNotIn('href="/logout/"', body)
                    self.assertIn('action="/logout/"', body)
                    self.assertIn('method="post"', body.lower())
