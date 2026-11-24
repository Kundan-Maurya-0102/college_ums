"""Do the notification channels actually leave the deployment?

Phase B found e-mail had no configuration at all: Django fell back to SMTP on
localhost:25, and 'sms' was quietly sent over the WhatsApp sender. These tests pin
the behaviour so a "Done" notification claim stays true.
"""
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings

from students import tasks

BASE = Path(settings.BASE_DIR)


class EmailSettingsTests(SimpleTestCase):
    def test_development_does_not_pretend_to_send_real_mail(self):
        """DEBUG=True must print mails, not try to reach an SMTP server."""
        backend = settings.EMAIL_BACKEND
        self.assertTrue(
            backend.endswith(('console.EmailBackend', 'locmem.EmailBackend')),
            f"dev backend should be console/locmem, got {backend}")

    def test_default_from_address_is_branded_and_not_broken(self):
        """A 'from' of 'webmaster@localhost' lands in spam (or bounces)."""
        self.assertTrue(settings.DEFAULT_FROM_EMAIL)
        self.assertIn('@', settings.DEFAULT_FROM_EMAIL)
        self.assertNotIn('webmaster@localhost', settings.DEFAULT_FROM_EMAIL)
        self.assertNotIn('www.', settings.DEFAULT_FROM_EMAIL)

    def test_production_defaults_to_smtp(self):
        """With DEBUG=False and no override, mail must attempt real delivery."""
        env = {
            **os.environ,
            'SECRET_KEY': 'x' * 60,
            'DEBUG': 'False',
            'ALLOWED_HOSTS': 'example.com',
            'CSRF_TRUSTED_ORIGINS': 'https://example.com',
            'EMAIL_BACKEND': '',
            'SENTRY_DSN': '',
        }
        code = ("import django, os; "
                "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'college_ums.settings'); "
                "django.setup(); "
                "from django.conf import settings; print(settings.EMAIL_BACKEND)")
        out = subprocess.run([sys.executable, '-c', code],
                             cwd=BASE, env=env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr[-400:])
        self.assertIn('smtp.EmailBackend', out.stdout)

    def test_tls_and_ssl_together_are_rejected(self):
        env = {
            **os.environ,
            'SECRET_KEY': 'x' * 60,
            'DEBUG': 'False',
            'ALLOWED_HOSTS': 'example.com',
            'CSRF_TRUSTED_ORIGINS': 'https://example.com',
            'EMAIL_USE_TLS': 'True',
            'EMAIL_USE_SSL': 'True',
            'SENTRY_DSN': '',
        }
        out = subprocess.run([sys.executable, 'manage.py', 'check'], cwd=BASE, env=env,
                             capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn('EMAIL_USE_TLS and EMAIL_USE_SSL', out.stdout + out.stderr)

    def test_env_example_documents_every_email_key(self):
        text = (BASE / '.env.example').read_text()
        for key in ('EMAIL_BACKEND', 'EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_HOST_USER',
                    'EMAIL_HOST_PASSWORD', 'EMAIL_USE_TLS', 'DEFAULT_FROM_EMAIL',
                    'TWILIO_SMS_FROM'):
            self.assertIn(key, text, f'{key} missing from .env.example')


class EmailTaskTests(TestCase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_email_task_reports_a_real_send(self):
        from django.core import mail

        result = tasks.send_email_task('student@example.com', 'Subject', 'Body')
        self.assertEqual(result, 'sent (1)')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(mail.outbox[0].to, ['student@example.com'])

    def test_email_task_without_address_is_skipped(self):
        self.assertEqual(tasks.send_email_task('', 'S', 'B'), 'skipped (no address)')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                       TASK_MAX_ATTEMPTS=1)
    def test_email_failure_is_reported_not_swallowed_silently(self):
        with mock.patch('django.core.mail.backends.locmem.EmailBackend.send_messages',
                        side_effect=OSError('connection refused')):
            with self.assertRaises(OSError):
                tasks.send_email_task('student@example.com', 'S', 'B')


class SmsChannelTests(TestCase):
    """'sms' must not be WhatsApp wearing another name."""

    @override_settings(TWILIO_ACCOUNT_SID='AC123', TWILIO_AUTH_TOKEN='token',
                       TWILIO_SMS_FROM='+919876543210')
    def test_sms_uses_plain_sender_and_plain_number(self):
        sent = {}

        class FakeMessages:
            def create(self, **kwargs):
                sent.update(kwargs)
                return mock.Mock(sid='SM123')

        client = mock.Mock(messages=FakeMessages())
        with mock.patch.object(tasks, '_make_twilio_client', return_value=client):
            result = tasks.send_sms_task('9876543210', 'Hello')
        self.assertEqual(result, 'sent (SM123)')
        self.assertEqual(sent['from_'], '+919876543210')
        self.assertEqual(sent['to'], '+919876543210'.replace('+919876543210', '+919876543210'))
        self.assertNotIn('whatsapp:', sent['to'])
        self.assertNotIn('whatsapp:', sent['from_'])

    @override_settings(TWILIO_ACCOUNT_SID='AC123', TWILIO_AUTH_TOKEN='token',
                       TWILIO_SMS_FROM='')
    def test_sms_without_sender_is_skipped_not_downgraded(self):
        with mock.patch.object(tasks, '_make_twilio_client') as factory:
            result = tasks.send_sms_task('9876543210', 'Hello')
        self.assertIn('SMS sender', result)
        factory.assert_not_called()

    @override_settings(TWILIO_ACCOUNT_SID='AC123', TWILIO_AUTH_TOKEN='token',
                       TWILIO_WHATSAPP_FROM='whatsapp:+14155238886')
    def test_whatsapp_keeps_the_whatsapp_prefix(self):
        sent = {}

        class FakeMessages:
            def create(self, **kwargs):
                sent.update(kwargs)
                return mock.Mock(sid='SM456')

        client = mock.Mock(messages=FakeMessages())
        with mock.patch.object(tasks, '_make_twilio_client', return_value=client):
            result = tasks.send_whatsapp_task('9876543210', 'Hello')
        self.assertEqual(result, 'sent (SM456)')
        self.assertEqual(sent['to'], 'whatsapp:+919876543210')
        self.assertEqual(sent['from_'], 'whatsapp:+14155238886')

    @override_settings(Q_SYNC=True, TWILIO_ACCOUNT_SID='', TWILIO_AUTH_TOKEN='')
    def test_notify_routes_each_channel_to_its_own_task(self):
        with mock.patch.object(tasks, 'send_sms_task', return_value='sent (x)') as sms:
            tasks.notify('sms', '9876543210', body='Body')
            sms.assert_called_once()
        with mock.patch.object(tasks, 'send_whatsapp_task', return_value='sent (y)') as wa:
            tasks.notify('whatsapp', '9876543210', body='Body')
            wa.assert_called_once()
        self.assertEqual(tasks.notify('carrier-pigeon', 'x')[0], 'failed')


class CheckEmailCommandTests(TestCase):
    def run_command(self, *args):
        out = StringIO()
        call_command('check_email', *args, stdout=out, stderr=out)
        return out.getvalue()

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_dry_run_reports_configuration_and_sends_nothing(self):
        from django.core import mail

        text = self.run_command('admin@example.com', '--dry-run')
        self.assertIn('backend', text)
        self.assertIn('dry run', text)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_real_send_reaches_the_outbox(self):
        from django.core import mail

        text = self.run_command('admin@example.com')
        self.assertIn('sent 1 message', text)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_console_backend_is_labeled_as_not_delivering(self):
        text = self.run_command('admin@example.com', '--dry-run')
        self.assertIn('console', text)

    def test_smtp_failure_raises_a_clear_error(self):
        with mock.patch('students.management.commands.check_email.send_mail',
                        side_effect=OSError('connection refused')):
            with self.assertRaises(CommandError) as ctx:
                self.run_command('admin@example.com')
        self.assertIn('connection refused', str(ctx.exception))
