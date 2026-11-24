"""Regression tests for BACKLOG.md items 1-3 (media, superuser, lockout UX)."""
import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from students.forms import AdminUserForm
from students.models import StudentProfile

User = get_user_model()
MEDIA = tempfile.mkdtemp(prefix='ums-media-test-')


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


def _write(relative, content=b'data'):
    path = os.path.join(MEDIA, relative)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(content)
    return path


@override_settings(MEDIA_ROOT=MEDIA, MEDIA_PROTECTED=True)
class ProtectedMediaTests(TestCase):
    """Item 1: uploaded files must never be readable without a login."""

    def setUp(self):
        _write('csv_uploads/2026/students.csv', b'name,reg\nAarav,CS001\n')
        _write('banners/fest.jpg', b'jpegbytes')
        self.student = User.objects.create_user('media_student', password='Xyz@12345')
        StudentProfile.objects.create(user=self.student, name='M', registration_number='M001',
                                      is_password_changed=True)
        self.staff = User.objects.create_user('media_staff', password='Xyz@12345',
                                              is_staff=True)

    def test_anonymous_visitor_is_redirected_to_login(self):
        response = self.client.get('/media/banners/fest.jpg')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_staff_can_download_a_csv_import(self):
        self.client.force_login(self.staff)
        response = self.client.get('/media/csv_uploads/2026/students.csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'name,reg\nAarav,CS001\n')

    def test_student_cannot_read_the_csv_inbox(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get('/media/csv_uploads/2026/students.csv').status_code, 404)

    def test_student_can_read_their_own_material(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get('/media/banners/fest.jpg').status_code, 200)

    def test_path_traversal_is_blocked(self):
        self.client.force_login(self.staff)
        for path in ('/media/../manage.py', '/media/../../etc/passwd',
                     '/media/%2e%2e/%2e%2e/etc/passwd'):
            response = self.client.get(path)
            self.assertIn(response.status_code, (400, 404), path)

    def test_missing_file_is_404(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/media/banners/nope.jpg').status_code, 404)

    def test_caddyfile_no_longer_serves_media_from_disk(self):
        directives = [line.strip() for line in open('deploy/Caddyfile')
                      if line.strip() and not line.strip().startswith('#')]
        self.assertNotIn('file_server', directives)
        self.assertFalse(any('/srv/media' in line for line in directives))


class AdminFormSuperuserTests(TestCase):
    """Item 2: creating an admin must not silently grant superuser."""

    def _data(self, **extra):
        return {'username': 'clerk1', 'email': 'clerk@example.edu',
                'password': 'Str0ngPass!23', **extra}

    def test_plain_admin_is_not_a_superuser(self):
        form = AdminUserForm(self._data(), allow_superuser=False)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_superuser_can_grant_superuser_explicitly(self):
        form = AdminUserForm(self._data(is_superuser='on'), allow_superuser=True)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(user.is_superuser)

    def test_superuser_field_defaults_to_unchecked(self):
        form = AdminUserForm(self._data(), allow_superuser=True)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.save().is_superuser)

    def test_non_superuser_cannot_post_the_flag(self):
        """A crafted POST must not escalate: the field is dropped, not just hidden."""
        form = AdminUserForm(self._data(is_superuser='on'), allow_superuser=False)
        self.assertNotIn('is_superuser', form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.save().is_superuser)

    def test_editing_keeps_existing_superuser_flag(self):
        existing = User.objects.create_user('boss', password='Xyz@12345',
                                            is_staff=True, is_superuser=True)
        form = AdminUserForm({'username': 'boss', 'email': '', 'password': ''},
                             instance=existing, allow_superuser=False)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        existing.refresh_from_db()
        self.assertTrue(existing.is_superuser)


class LoginLockoutMessageTests(TestCase):
    """Item 3: a locked out user is told what happened and what to do next."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # the lockout counter lives in the cache
        self.client = Client(HTTP_HOST='localhost')
        User.objects.create_user('lockme', password='Correct@12345')

    def _fail_login(self, times):
        for _ in range(times):
            self.client.post('/login/', {'username': 'lockme', 'password': 'wrong'})

    def test_wrong_password_shows_attempts_left(self):
        response = self.client.post('/login/', {'username': 'lockme', 'password': 'wrong'})
        body = response.content.decode()
        self.assertIn('attempt(s) left', body)

    def test_last_attempt_mentions_the_set_password_link(self):
        self._fail_login(4)
        body = self.client.post('/login/', {'username': 'lockme', 'password': 'wrong'}
                                ).content.decode()
        self.assertIn('set-password link', body)

    def test_lockout_page_explains_and_counts_down(self):
        self._fail_login(5)
        body = self.client.post('/login/', {'username': 'lockme', 'password': 'Correct@12345'}
                                ).content.decode()
        self.assertIn('locked', body.lower())
        self.assertIn('data-lockout-remaining', body)   # countdown hook
        self.assertIn('set-password link', body)

    def test_correct_password_works_after_counter_reset(self):
        from students.security import reset_login_failures

        self._fail_login(3)
        request = self.client.post('/login/', {'username': 'lockme', 'password': 'wrong'})
        reset_login_failures(request.wsgi_request, 'lockme')
        response = self.client.post('/login/', {'username': 'lockme', 'password': 'Correct@12345'})
        self.assertEqual(response.status_code, 302)
