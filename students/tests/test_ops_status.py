"""System status page, error tracking, digest e-mail, diagnose command, backups."""
import json
import logging
import shutil
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from students.error_tracking import DatabaseErrorHandler, fingerprint_for
from students.models import BackupRecord, ErrorEvent, StudentProfile

User = get_user_model()


class ErrorTrackingTests(TestCase):
    def emit(self, logger_name='django.request', message='boom'):
        record = logging.LogRecord(logger_name, logging.ERROR, 'x.py', 1, message, None, None)
        DatabaseErrorHandler().emit(record)

    def test_error_record_is_stored(self):
        self.emit()
        event = ErrorEvent.objects.get()
        self.assertEqual(event.level, 'ERROR')
        self.assertEqual(event.message, 'boom')
        self.assertEqual(event.count, 1)

    def test_repeated_error_increments_one_row(self):
        self.emit()
        self.emit()
        event = ErrorEvent.objects.get()
        self.assertEqual(event.count, 2)
        self.assertEqual(ErrorEvent.objects.count(), 1)

    def test_warnings_and_info_are_ignored(self):
        for level in (logging.WARNING, logging.INFO, logging.DEBUG):
            record = logging.LogRecord('x', level, 'x.py', 1, 'nope', None, None)
            DatabaseErrorHandler().emit(record)
        self.assertEqual(ErrorEvent.objects.count(), 0)

    def test_critical_is_stored_as_critical(self):
        record = logging.LogRecord('x', logging.CRITICAL, 'x.py', 1, 'very bad', None, None)
        DatabaseErrorHandler().emit(record)
        self.assertEqual(ErrorEvent.objects.get().level, 'CRITICAL')

    def test_long_message_is_truncated(self):
        self.emit(message='x' * 5000)
        self.assertLessEqual(len(ErrorEvent.objects.get().message), 1000)

    def test_logging_failure_never_raises(self):
        with mock.patch('students.models.ErrorEvent.objects.get_or_create',
                        side_effect=RuntimeError('db is gone')):
            self.emit()  # must not raise
        self.assertEqual(ErrorEvent.objects.count(), 0)

    def test_handler_can_be_disabled(self):
        with override_settings(ERROR_TRACKING_ENABLED=False):
            self.emit()
        self.assertEqual(ErrorEvent.objects.count(), 0)

    def test_fingerprint_is_stable_and_path_sensitive(self):
        one = fingerprint_for('django.request', 'boom', '/a/')
        self.assertEqual(one, fingerprint_for('django.request', 'boom', '/a/'))
        self.assertNotEqual(one, fingerprint_for('django.request', 'boom', '/b/'))

    def test_handler_is_wired_into_settings(self):
        from django.conf import settings

        handlers = settings.LOGGING['root']['handlers']
        self.assertIn('errors_db', handlers)
        self.assertEqual(settings.LOGGING['handlers']['errors_db']['level'], 'ERROR')


class SystemStatusPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='office', password='TestPass@12345', is_staff=True)
        cls.student_user = User.objects.create_user(username='stud', password='TestPass@12345')
        StudentProfile.objects.create(
            user=cls.student_user, name='Status Student', registration_number='SS001',
            branch='CS', semester=3, is_password_changed=True)

    def login(self, user=None):
        client = Client(HTTP_HOST='localhost')
        client.force_login(user or self.admin)
        return client

    def test_page_requires_staff(self):
        response = self.login(self.student_user).get(reverse('system_status'))
        self.assertIn(response.status_code, (302, 403))

    def test_anonymous_redirected(self):
        response = Client(HTTP_HOST='localhost').get(reverse('system_status'))
        self.assertEqual(response.status_code, 302)

    def test_page_shows_measured_facts(self):
        BackupRecord.objects.create(path=Path(tempfile.gettempdir()) / 'x.sql.gz.enc',
                                    size_bytes=2048, encrypted=True)
        ErrorEvent.objects.create(level='ERROR', logger_name='django.request',
                                  message='a real problem', fingerprint='fp1')
        response = self.login().get(reverse('system_status'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('System status', body)
        self.assertIn('Database', body)
        self.assertIn('Last backup', body)
        self.assertIn('Background jobs', body)
        self.assertIn('a real problem', body)
        self.assertIn('SS001' if False else 'students', body.lower())

    def test_stale_backup_is_flagged(self):
        old = timezone.now() - timedelta(hours=100)
        record = BackupRecord.objects.create(
            path=str(Path(tempfile.gettempdir()) / 'old.sql.gz.enc'), size_bytes=1)
        BackupRecord.objects.filter(pk=record.pk).update(created_at=old)
        with override_settings(BACKUP_MAX_AGE_HOURS=48):
            body = self.login().get(reverse('system_status')).content.decode()
        self.assertIn('older than expected', body)

    def test_missing_email_config_is_visible(self):
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'):
            body = self.login().get(reverse('system_status')).content.decode()
        self.assertIn('not configured', body)


class ErrorDigestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_superuser(
            username='owner', password='TestPass@12345', email='owner@example.com')

    def add_error(self, message='something broke', count=1):
        return ErrorEvent.objects.create(
            level='ERROR', logger_name='django.request', message=message,
            fingerprint=message[:20], count=count)

    def run_command(self, *args):
        out = StringIO()
        call_command('send_error_digest', *args, stdout=out, stderr=out)
        return out.getvalue()

    def test_quiet_day_sends_nothing_with_only_if_errors(self):
        text = self.run_command('--only-if-errors')
        self.assertIn('no errors', text)
        self.assertNotIn('queued to', text)

    def test_digest_queues_mail_to_superusers(self):
        self.add_error(count=7)
        with mock.patch('students.management.commands.send_error_digest.notify',
                        return_value=('queued', 'id1')) as notify:
            text = self.run_command()
        self.assertIn('queued to owner@example.com', text)
        subject = notify.call_args[0][2]
        body = notify.call_args[0][3]
        self.assertIn('1 error(s)', subject)
        self.assertIn('something broke', body)
        self.assertIn('total occurrences: 7', body)

    def test_support_email_overrides_recipients(self):
        self.add_error()
        with override_settings(SUPPORT_EMAIL='support@example.com'), \
                mock.patch('students.management.commands.send_error_digest.notify',
                           return_value=('queued', 'id')) as notify:
            self.run_command()
        self.assertEqual(notify.call_args[0][1], 'support@example.com')

    def test_old_errors_stay_out_of_the_window(self):
        event = self.add_error()
        ErrorEvent.objects.filter(pk=event.pk).update(
            last_seen=timezone.now() - timedelta(hours=48))
        text = self.run_command('--hours', '24', '--only-if-errors')
        self.assertIn('no errors', text)

    def test_resolved_errors_are_skipped_by_default(self):
        event = self.add_error()
        ErrorEvent.objects.filter(pk=event.pk).update(is_resolved=True)
        self.assertIn('no errors', self.run_command('--only-if-errors'))

    def test_to_override_and_dry_run(self):
        self.add_error()
        text = self.run_command('--to', 'someone@example.com', '--dry-run')
        self.assertIn('dry run', text)
        self.assertIn('something broke', text)


class DiagnoseCollegeTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_json(self, *args):
        out = StringIO()
        code = 0
        try:
            call_command('diagnose_college', *args, '--json', '--skip-network', stdout=out)
        except SystemExit as exc:
            code = exc.code
        return json.loads(out.getvalue()), code

    def test_report_covers_the_documented_areas(self):
        payload, _code = self.run_json('localhost')
        names = {c['name'] for c in payload['checks']}
        for expected in ('Database', 'Migrations', 'Static files', 'E-mail',
                         'WhatsApp (Twilio)', 'Disk space', 'Cache'):
            self.assertIn(expected, names)
        self.assertIn('ok', payload)

    def test_domain_outside_allowed_hosts_is_broken(self):
        payload, code = self.run_json('not-configured.example')
        domain_check = next(c for c in payload['checks'] if c['name'] == 'Domain/ALLOWED_HOSTS')
        self.assertEqual(domain_check['status'], 'BROKEN')
        self.assertEqual(code, 1)

    def test_configured_domain_passes(self):
        payload, _code = self.run_json('localhost')
        domain_check = next(c for c in payload['checks'] if c['name'] == 'Domain/ALLOWED_HOSTS')
        self.assertEqual(domain_check['status'], 'OK')

    def test_console_email_backend_in_production_is_broken(self):
        with override_settings(DEBUG=False,
                               EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'):
            payload, _code = self.run_json()
        email = next(c for c in payload['checks'] if c['name'] == 'E-mail')
        self.assertEqual(email['status'], 'BROKEN')

    def test_missing_static_manifest_is_broken(self):
        with override_settings(STATIC_ROOT=str(self.tmp)):
            payload, _code = self.run_json()
        static = next(c for c in payload['checks'] if c['name'] == 'Static files')
        self.assertEqual(static['status'], 'BROKEN')

    def test_unwritable_media_is_broken(self):
        media = self.tmp / 'media'
        media.mkdir()
        with override_settings(MEDIA_ROOT=str(media)), \
                mock.patch('os.access', return_value=False):
            payload, _code = self.run_json()
        check = next(c for c in payload['checks'] if c['name'] == 'Media folder')
        self.assertEqual(check['status'], 'BROKEN')

    def test_missing_backup_is_a_warning_not_a_crash(self):
        payload, _code = self.run_json()
        backup = next(c for c in payload['checks'] if c['name'] == 'Backups')
        self.assertEqual(backup['status'], 'WARN')


class RecordBackupTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.file = self.tmp / 'ums-20260101.sql.gz.enc'
        self.file.write_bytes(b'dump-contents')

    def test_records_size_checksum_and_encryption(self):
        out = StringIO()
        call_command('record_backup', '--path', str(self.file), stdout=out)
        record = BackupRecord.objects.get()
        self.assertEqual(record.size_bytes, 13)
        self.assertTrue(record.encrypted)
        self.assertEqual(len(record.checksum), 64)
        self.assertEqual(record.kind, 'database')

    def test_missing_file_fails_clearly(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command('record_backup', '--path', str(self.tmp / 'nope.sql'), stdout=StringIO())

    def test_plain_dump_is_marked_unencrypted(self):
        plain = self.tmp / 'plain.sql.gz'
        plain.write_bytes(b'x')
        call_command('record_backup', '--path', str(plain), stdout=StringIO())
        self.assertFalse(BackupRecord.objects.get().encrypted)
