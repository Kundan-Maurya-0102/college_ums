"""Open redirect prevention: every user-supplied 'next' URL is validated."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from students.models import BugReport


class OpenRedirectTests(TestCase):
    """POST to report_problem with various malicious 'next' values."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='redirect_tester', password='Str0ng!Pass1',
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.url = reverse('report_problem')
        self.base_data = {
            'category': 'bug',
            'message': 'Test bug report for redirect',
        }

    def _post(self, next_val):
        data = {**self.base_data}
        if next_val is not None:
            data['next'] = next_val
        return self.client.post(self.url, data)

    def test_absolute_evil_url_blocked(self):
        """https://evil.com must NOT appear in Location."""
        resp = self._post('https://evil.com/phish')
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn('evil.com', resp['Location'])

    def test_protocol_relative_url_blocked(self):
        """//evil.com must be rejected."""
        resp = self._post('//evil.com')
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn('evil.com', resp['Location'])

    def test_backslash_bypass_blocked(self):
        r"""/\evil.com must be rejected."""
        resp = self._post('/\\evil.com')
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn('evil.com', resp['Location'])

    def test_javascript_uri_blocked(self):
        resp = self._post('javascript:alert(1)')
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn('javascript', resp['Location'])

    def test_host_confusion_blocked(self):
        """http://localhost@evil.com is a redirect to evil.com."""
        resp = self._post('http://localhost@evil.com')
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn('evil.com', resp['Location'])

    def test_no_next_param_uses_default(self):
        resp = self._post(None)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('help', resp['Location'])

    def test_safe_relative_path_allowed(self):
        resp = self._post('/my-fees/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/my-fees/', resp['Location'])

    def test_empty_next_uses_default(self):
        resp = self._post('')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('help', resp['Location'])
