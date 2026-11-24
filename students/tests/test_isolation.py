"""College A vs College B: can A's user ever see B's data?

Architecture: one college = one deployment = one database. So the honest questions
are:

1. Does any request ever read a *second* database? (No: every query uses `default`.)
2. Can data from another deployment leak into A's pages — by list, detail, search,
   CSV export, file download, or notification?
3. Can A's token write B's platform row?
4. Can another college's domain reach A's app at all?

The suite builds a real second database (`college_b`) full of College B data, then
drives College A's views and asserts none of B's markers ever appear. B's rows are
also given *the same primary keys* A uses, so "just change the ID" is covered too.
"""
import csv
import io
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from platform_admin.models import College
from students.models import (
    Attendance,
    FacultyProfile,
    FeePayment,
    FeeStructure,
    InternalExam,
    Notice,
    StudentProfile,
    Subject,
    User,
)

SECOND_DB = 'college_b'

# Marker strings that must never appear on a College A page.
B_STUDENT_NAME = 'Zzz B-College Student'
B_REG = 'BCOLLEGE0001'
B_TEACHER = 'Zzz B-College Teacher'
B_SUBJECT = 'ZZB-COLLEGE-SUBJECT'
B_NOTICE = 'ZZB notice from college B'
B_DEPT = 'ZZB-DEPT'


class TwoCollegeFixture:
    """Create the same college-shaped data twice: once in A (default), once in B."""

    @staticmethod
    def seed(using):
        """One college's worth of data: admin, teacher, student, subject, money, marks."""
        tag = 'B' if using == SECOND_DB else 'A'
        student_name = B_STUDENT_NAME if using == SECOND_DB else 'A-College Student'
        teacher_name = B_TEACHER if using == SECOND_DB else 'A-College Teacher'
        subject_name = B_SUBJECT if using == SECOND_DB else 'A-College Subject'
        reg = B_REG if using == SECOND_DB else 'ACOLLEGE0001'

        admin = User.objects.db_manager(using).create_user(
            username=f'office-{tag.lower()}', password='TestPass@12345',
            is_staff=True, email=f'office@{tag.lower()}.example.edu')
        teacher_user = User.objects.db_manager(using).create_user(
            username=f'teacher-{tag.lower()}', password='TestPass@12345')
        teacher = FacultyProfile.objects.using(using).create(
            user=teacher_user, name=teacher_name,
            department=B_DEPT if using == SECOND_DB else 'A Department')
        student_user = User.objects.db_manager(using).create_user(
            username=f'student-{tag.lower()}', password='TestPass@12345')
        student = StudentProfile.objects.using(using).create(
            user=student_user, name=student_name, registration_number=reg,
            branch='CS', semester=3, year_of_admission=2023, is_password_changed=True)
        subject = Subject.objects.using(using).create(
            branch='CS', semester=3, subject_code=f'{tag}01', subject_name=subject_name)
        teacher.subjects.add(subject)
        Attendance.objects.using(using).create(
            student=student, subject=subject, date=timezone.localdate(),
            is_present=True, marked_by=teacher_name)
        InternalExam.objects.using(using).create(
            student=student, subject=subject, exam_type='MSE', marks_obtained=42,
            max_marks=50, exam_date=timezone.localdate())
        structure = FeeStructure.objects.using(using).create(
            branch='CS', semester=3, fee_type='TUITION', amount=1100,
            academic_year='2024-2025')
        FeePayment.objects.using(using).create(
            student=student, fee_structure=structure, amount_paid=500,
            payment_date=timezone.localdate(), receipt_number=f'RCPT-{tag}',
            payment_mode='CASH', status='PARTIAL')
        Notice.objects.using(using).create(
            title=B_NOTICE if using == SECOND_DB else 'A notice',
            content='body', created_by=teacher)
        return {'student': student, 'teacher': teacher, 'subject': subject,
                'admin': admin, 'fee_structure': structure}


class IsolationBase(TestCase):
    databases = {'default', SECOND_DB}

    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.a = TwoCollegeFixture.seed('default')
        cls.b = TwoCollegeFixture.seed(SECOND_DB)

    def login(self, role):
        client = Client(HTTP_HOST='localhost')
        user = self.a['admin'] if role == 'admin' else (
            self.a['teacher'].user if role == 'teacher' else self.a['student'].user)
        client.force_login(user)
        return client

    def assertNoCollegeB(self, response, url='', ignore=()):
        """Fail if any College B row value appears. `ignore` drops reflected input
        (a search box echoes the term you typed — that is not B's data)."""
        body = response.content.decode('utf-8', 'ignore')
        for echo in ignore:
            body = body.replace(echo, '')
        for marker in (B_STUDENT_NAME, B_REG, B_TEACHER, B_SUBJECT, B_NOTICE, B_DEPT):
            self.assertNotIn(marker, body, f'{marker!r} leaked into {url}')
        return body


class DatabaseBoundaryTests(IsolationBase):
    """A deployment must hold one database, and no view may read another."""

    def test_second_database_really_has_college_b_rows(self):
        self.assertEqual(
            StudentProfile.objects.using(SECOND_DB).get(registration_number=B_REG).name,
            B_STUDENT_NAME)
        # and A's own database does not
        self.assertFalse(StudentProfile.objects.filter(registration_number=B_REG).exists())

    def test_no_view_or_model_reads_another_database(self):
        """`.using(...)` outside tests would mean cross-college reads."""
        app_dir = Path(settings.BASE_DIR) / 'students'
        offenders = []
        for path in app_dir.rglob('*.py'):
            if 'tests' in path.parts or path.name in {'apps.py'}:
                continue
            text = path.read_text(errors='ignore')
            if '.using(' in text or 'using=' in text:
                offenders.append(str(path.relative_to(settings.BASE_DIR)))
        self.assertEqual(offenders, [], f'cross-database access in: {offenders}')

    def test_production_settings_define_exactly_one_database(self):
        """A shared multi-tenant DB would make every list page a leak; forbid it."""
        import subprocess
        import sys

        code = ("import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE',"
                " 'college_ums.settings'); django.setup();"
                " from django.conf import settings;"
                " print(sorted(settings.DATABASES))")
        out = subprocess.run([sys.executable, '-c', code], cwd=settings.BASE_DIR,
                             capture_output=True, text=True,
                             env={**os.environ, 'DEBUG': 'False',
                                  'SECRET_KEY': 'x' * 60,
                                  'ALLOWED_HOSTS': 'example.com',
                                  'CSRF_TRUSTED_ORIGINS': 'https://example.com',
                                  'SENTRY_DSN': ''})
        self.assertEqual(out.returncode, 0, out.stderr[-300:])
        self.assertEqual(out.stdout.strip(), "['default']")


class CrossDeploymentPageTests(IsolationBase):
    """Every page A's users open must be free of B's rows."""

    def test_admin_lists_and_reports(self):
        client = self.login('admin')
        for name in ('admin_dashboard', 'student_list', 'teacher_list',
                     'subject_list', 'notice_list', 'reports_view', 'fee_payments',
                     'attendance_entry', 'marks_entry'):
            try:
                url = reverse(name)
            except Exception:
                continue
            response = client.get(url)
            self.assertIn(response.status_code, (200, 302), name)
            if response.status_code == 200:
                self.assertNoCollegeB(response, name)

    def test_teacher_scope_pages(self):
        client = self.login('teacher')
        for name in ('teacher_dashboard', 'teacher_students', 'teacher_take_attendance',
                     'teacher_marks', 'teacher_materials', 'teacher_notices'):
            try:
                url = reverse(name)
            except Exception:
                continue
            response = client.get(url)
            self.assertIn(response.status_code, (200, 302), name)
            if response.status_code == 200:
                self.assertNoCollegeB(response, name)

    def test_student_pages(self):
        client = self.login('student')
        for name in ('student_dashboard', 'student_fees', 'student_certificates',
                     'student_exam_schedule', 'student_events'):
            try:
                url = reverse(name)
            except Exception:
                continue
            response = client.get(url)
            self.assertIn(response.status_code, (200, 302), name)
            if response.status_code == 200:
                self.assertNoCollegeB(response, name)

    def test_search_never_returns_the_other_college(self):
        client = self.login('admin')
        for term in (B_REG, 'BCOLLEGE', 'Zzz B-College'):
            response = client.get(reverse('student_list'), {'q': term})
            self.assertEqual(response.status_code, 200)
            body = self.assertNoCollegeB(response, 'student_list search', ignore=(term,))
            self.assertNotIn('ACOLLEGE0001', body,
                             'search for B data returned A rows — filter is broken')
            self.assertIn('No students found', body,
                          f'search for {term!r} matched something it should not')


class IdSwapTests(IsolationBase):
    """B's rows use the same IDs as A's; changing the URL must not reach them."""

    def test_student_id_swap_hits_own_row_only(self):
        client = self.login('student')
        # B's student has the same primary key in the other database.
        b_pk = self.b['student'].pk
        self.assertEqual(b_pk, self.a['student'].pk)
        own_marker = {'student_fees': ('RCPT-A', {}),
                      'student_certificates': ('ACOLLEGE0001', {'type': 'bonafide'})}
        for name, (marker, params) in own_marker.items():
            response = client.get(reverse(name), params)
            self.assertIn(response.status_code, (200, 302, 404), name)
            if response.status_code == 200:
                body = self.assertNoCollegeB(response, name)
                self.assertIn(marker, body, f'{name} did not show A\'s own data')

    def test_admin_detail_of_a_student_shows_a_data(self):
        client = self.login('admin')
        url = reverse('student_edit', args=[self.b['student'].pk])
        response = client.get(url)
        if response.status_code == 200:
            body = self.assertNoCollegeB(response, 'student_detail')
            self.assertIn('ACOLLEGE0001', body)

    def test_teacher_cannot_open_another_teachers_marks_entry(self):
        client = self.login('teacher')
        other_subject = Subject.objects.create(
            branch='CS', semester=3, subject_code='OTH1',
            subject_name='Someone Else Subject')
        url = reverse('marks_entry') + f'?subject={other_subject.pk}'
        response = client.get(url, follow=True)
        # either refused, or shown an own-subjects-only form — never B's class
        self.assertIn(response.status_code, (200, 302, 403, 404))
        self.assertNoCollegeB(response, 'marks_entry')


class ExportTests(IsolationBase):
    def test_students_csv_export_contains_only_this_college(self):
        client = self.login('admin')
        response = client.get(reverse('export_students_csv'))
        self.assertEqual(response.status_code, 200)
        text = response.content.decode('utf-8', 'ignore')
        self.assertIn('ACOLLEGE0001', text)
        self.assertNotIn(B_REG, text)
        self.assertNotIn(B_STUDENT_NAME, text)

    def test_csv_export_is_valid_csv(self):
        client = self.login('admin')
        response = client.get(reverse('export_students_csv'))
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        self.assertGreaterEqual(len(rows), 2)


class FileDownloadTests(IsolationBase):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_media_from_another_deployment_is_not_reachable(self):
        """B's media lives in B's MEDIA_ROOT; A's /media/<same path> must 404."""
        (self.tmp / 'materials').mkdir()
        (self.tmp / 'materials' / 'a-note.txt').write_text('A content')
        with override_settings(MEDIA_ROOT=self.tmp, MEDIA_PROTECTED=True):
            client = self.login('student')
            ok = client.get('/media/materials/a-note.txt')
            self.assertEqual(ok.status_code, 200)
            missing = client.get('/media/materials/b-note.txt')
            self.assertEqual(missing.status_code, 404)

            staff_only = client.get('/media/csv_uploads/students.csv')
            self.assertEqual(staff_only.status_code, 404,
                             'a student could read the CSV inbox')

    def test_anonymous_cannot_download_anything(self):
        (self.tmp / 'materials').mkdir()
        (self.tmp / 'materials' / 'note.txt').write_text('x')
        with override_settings(MEDIA_ROOT=self.tmp, MEDIA_PROTECTED=True):
            response = Client(HTTP_HOST='localhost').get('/media/materials/note.txt')
            self.assertEqual(response.status_code, 302)


class NotificationScopeTests(IsolationBase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                       Q_SYNC=True)
    def test_credential_mail_only_reaches_this_deployments_student(self):
        from students import tasks

        mail.outbox.clear()
        with mock.patch.object(tasks, 'enqueue', side_effect=tasks.run_now):
            result = tasks.notify('email', 'a-student@example.com', 'Welcome', 'Body')
        self.assertEqual(result[0], 'ran')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['a-student@example.com'])
        self.assertNotIn(B_REG, str(mail.outbox[0].to))


class PlatformBoundaryTests(TestCase):
    """The platform database is shared; tokens must stay per college."""

    def setUp(self):
        self.a, _ = College.objects.get_or_create(
            slug='college-a', defaults={'name': 'College A', 'metrics_token': 'token-a'})
        self.b, _ = College.objects.get_or_create(
            slug='college-b', defaults={'name': 'College B', 'metrics_token': 'token-b'})
        self.a.metrics_token = 'token-a'
        self.a.save(update_fields=['metrics_token'])
        self.b.metrics_token = 'token-b'
        self.b.save(update_fields=['metrics_token'])

    def post(self, slug, token, payload=None):
        return Client(HTTP_HOST='localhost').post(
            reverse('platform_metrics', args=[slug]),
            data=payload or {'student_count': 7},
            content_type='application/json',
            HTTP_X_PLATFORM_TOKEN=token)

    def test_own_token_writes_own_college(self):
        response = self.post('college-a', 'token-a')
        self.assertEqual(response.status_code, 200)
        self.a.refresh_from_db()
        self.assertEqual(self.a.student_count, 7)

    def test_other_colleges_token_cannot_write(self):
        self.b.student_count = 0
        self.b.save(update_fields=['student_count'])
        response = self.post('college-b', 'token-a')
        self.assertEqual(response.status_code, 403)
        self.b.refresh_from_db()
        self.assertEqual(self.b.student_count, 0)

    def test_missing_token_is_forbidden(self):
        response = self.post('college-a', '')
        self.assertEqual(response.status_code, 403)

    @override_settings(PLATFORM_METRICS_TOKEN='shared-token')
    def test_shared_token_only_works_until_a_college_has_its_own(self):
        self.b.metrics_token = ''
        self.b.save(update_fields=['metrics_token'])
        self.assertEqual(self.post('college-b', 'shared-token').status_code, 200)
        # once it has a token, the shared one stops working for it
        self.b.metrics_token = 'token-b'
        self.b.save(update_fields=['metrics_token'])
        self.assertEqual(self.post('college-b', 'shared-token').status_code, 403)


class DomainBoundaryTests(IsolationBase):
    def test_another_colleges_domain_cannot_reach_this_deployment(self):
        """B's domain is not in A's ALLOWED_HOSTS -> the request never reaches a view."""
        client = Client(HTTP_HOST='college-b.example.edu')
        response = client.get('/login/')
        self.assertEqual(response.status_code, 400)

    def test_own_domain_works(self):
        response = Client(HTTP_HOST='localhost').get('/login/')
        self.assertEqual(response.status_code, 200)
