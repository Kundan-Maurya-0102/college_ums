"""Certificate generation page tests."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from students.models import StudentProfile


class CertificatePageTests(TestCase):
    """Verify the certificates page renders for a student."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cert_student', password='Str0ng!Pass1',
        )
        self.profile = StudentProfile.objects.create(
            user=self.user, name='Cert Student', phone='9876543210',
            registration_number='CT001', branch='CS', semester=3,
            is_password_changed=True,
        )

    def test_student_can_access_certificates_page(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('student_certificates'))
        self.assertEqual(resp.status_code, 200)

    def test_certificates_page_shows_student_info(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('student_certificates'))
        self.assertContains(resp, 'CT001')

    def test_certificate_type_filter(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('student_certificates') + '?type=bonafide')
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(reverse('student_certificates'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    def test_admin_redirected_away(self):
        admin = User.objects.create_user(
            username='cert_admin', password='Admin@12345', is_staff=True,
        )
        self.client.force_login(admin)
        resp = self.client.get(reverse('student_certificates'))
        self.assertEqual(resp.status_code, 302)
