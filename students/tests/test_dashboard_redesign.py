"""Student dashboard redesign: one screen, only my data, a bounded number of queries."""
from datetime import time as dt_time
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from students.models import (
    Assignment,
    Attendance,
    ClassSchedule,
    DashboardSettings,
    Event,
    ExamSchedule,
    FacultyProfile,
    FeePayment,
    FeeStructure,
    InternalExam,
    Notice,
    SemesterResult,
    StudentProfile,
    StudyMaterial,
    Subject,
)

User = get_user_model()


def make_student(username, reg, name, branch='CS', semester=3):
    user = User.objects.create_user(username=username, password='TestPass@12345')
    return StudentProfile.objects.create(
        user=user, name=name, registration_number=reg, branch=branch,
        semester=semester, year_of_admission=2023, is_password_changed=True)


class DashboardFixture:
    """One populated student plus another student who must never be visible."""

    @staticmethod
    def seed():
        faculty_user = User.objects.create_user(username='fac-dash', password='TestPass@12345')
        faculty = FacultyProfile.objects.create(user=faculty_user, name='Teacher Dash')

        mine = make_student('stu-mine', 'DASH001', 'My Student')
        other = make_student('stu-other', 'DASH999', 'Other Student')

        subject = Subject.objects.create(branch='CS', semester=3, subject_code='CS301',
                                        subject_name='Database Systems')
        # A different class entirely: nothing about it belongs on this student's page.
        other_subject = Subject.objects.create(branch='ME', semester=5, subject_code='ME501',
                                              subject_name='Other Subject')

        today = timezone.localdate()
        # my attendance: 3 of 4 held (75%)
        for i in range(3):
            Attendance.objects.create(student=mine, subject=subject,
                                      date=today - timedelta(days=i + 1), is_present=True)
        Attendance.objects.create(student=mine, subject=subject,
                                  date=today - timedelta(days=5), is_present=False)
        # other student's attendance must never influence my %
        for i in range(10):
            Attendance.objects.create(student=other, subject=subject,
                                      date=today - timedelta(days=i + 6), is_present=True)

        ClassSchedule.objects.create(subject=subject, faculty=faculty,
                                     weekday=today.weekday(),
                                     start_time=dt_time(hour=10), end_time=dt_time(hour=11),
                                     room='R-101')
        StudyMaterial.objects.create(title='My notes', subject=subject, uploaded_by=faculty)

        # marks / result only for me
        SemesterResult.objects.create(student=mine, semester=3, subject=subject,
                                      internal_marks=20, external_marks=60,
                                      total_marks=80, grade='A', is_pass=True)
        InternalExam.objects.create(student=mine, subject=subject, exam_type='MSE',
                                    marks_obtained=18, max_marks=20, exam_date=today)
        SemesterResult.objects.create(student=other, semester=5, subject=other_subject,
                                      internal_marks=5, external_marks=5,
                                      total_marks=10, grade='F', is_pass=False)

        structure = FeeStructure.objects.create(
            branch='CS', semester=3, fee_type='TUITION', amount=Decimal('5000'),
            academic_year='2024-2025', due_date=today + timedelta(days=10))
        FeePayment.objects.create(student=mine, fee_structure=structure,
                                  amount_paid=Decimal('2000'), payment_date=today,
                                  receipt_number='RCPT-DASH-1', status='PARTIAL')
        # another student's payment must not reduce my due amount
        FeePayment.objects.create(student=other, fee_structure=structure,
                                  amount_paid=Decimal('5000'), payment_date=today,
                                  receipt_number='RCPT-DASH-2', status='PAID')

        Assignment.objects.create(title='My assignment', subject=subject,
                                  assigned_by=faculty, due_date=today + timedelta(days=2))
        Assignment.objects.create(title='Other assignment', subject=other_subject,
                                  assigned_by=faculty, due_date=today + timedelta(days=2))

        Notice.objects.create(title='General notice', content='hello', created_by=faculty)
        Notice.objects.create(title='Class message', content='bring notebook',
                              created_by=faculty, target_branches='CS',
                              target_semesters='3')
        Notice.objects.create(title='Secret other class', content='hidden',
                              created_by=faculty, target_branches='ME',
                              target_semesters='5')

        Event.objects.create(title='Workshop', event_date=today + timedelta(days=3),
                             start_time=dt_time(hour=9), venue='Auditorium')
        ExamSchedule.objects.create(branch='CS', semester=3, subject=subject,
                                    exam_type='END_SEM', exam_date=today + timedelta(days=7),
                                    start_time=dt_time(hour=10), end_time=dt_time(hour=13))
        return {'mine': mine, 'other': other, 'subject': subject, 'faculty': faculty}


class DashboardAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DashboardFixture.seed()

    def login(self, profile):
        client = Client(HTTP_HOST='localhost')
        client.force_login(profile.user)
        return client

    def test_dashboard_renders_with_the_new_shell(self):
        response = self.login(self.data['mine']).get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for marker in ('dash-nav', 'dash-sidebar', 'dash-quick', 'dash-grid',
                       'My Courses', 'Announcements'):
            self.assertIn(marker, body)

    def test_dashboard_shows_only_my_numbers(self):
        body = self.login(self.data['mine']).get(reverse('student_dashboard')).content.decode()
        # my attendance is 75% (3 of 4) even though the other student has 10 more classes
        self.assertIn('75.0%', body)
        self.assertIn('3 of 4 classes', body)
        # my fee due is 5000-2000, not cancelled out by the other student's payment
        self.assertIn('3,000', body)
        # my assignment is listed, theirs is not
        self.assertIn('My assignment', body)
        self.assertNotIn('Other assignment', body)
        self.assertNotIn('Other Subject', body)
        self.assertNotIn('Other Student', body)

    def test_only_notices_for_my_class_are_shown(self):
        body = self.login(self.data['mine']).get(reverse('student_dashboard')).content.decode()
        self.assertIn('General notice', body)
        self.assertIn('Class message', body)
        self.assertNotIn('Secret other class', body)

    def test_staff_is_redirected_and_anonymous_sent_to_login(self):
        staff = User.objects.create_user(username='office-dash', password='TestPass@12345',
                                        is_staff=True)
        client = Client(HTTP_HOST='localhost')
        client.force_login(staff)
        self.assertEqual(client.get(reverse('student_dashboard')).url, reverse('admin_dashboard'))

        anonymous = Client(HTTP_HOST='localhost').get(reverse('student_dashboard'))
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn('/login/', anonymous['Location'])

    def test_unread_badge_counts_notices_then_clears(self):
        client = self.login(self.data['mine'])
        first = client.get(reverse('student_dashboard'))
        # everything is unread on the first visit, and the visit marks them seen
        self.assertIn('dash-badge-count', first.content.decode())
        profile = StudentProfile.objects.get(pk=self.data['mine'].pk)
        self.assertIsNotNone(profile.dashboard_seen_at)

        second = client.get(reverse('student_dashboard'))
        self.assertNotIn('dash-badge-count', second.content.decode())

    def test_hidden_cards_are_not_rendered(self):
        DashboardSettings.objects.update_or_create(
            pk=1, defaults={'hidden_cards': ['events', 'assignments']})
        body = self.login(self.data['mine']).get(reverse('student_dashboard')).content.decode()
        self.assertNotIn('Upcoming events', body)
        self.assertNotIn('Pending assignments', body)
        self.assertIn('My Courses', body)

    def test_pay_online_button_only_with_a_gateway(self):
        client = self.login(self.data['mine'])
        body = client.get(reverse('student_dashboard')).content.decode()
        self.assertNotIn('Pay online', body)
        self.assertIn('Contact accounts', body)

        with override_settings(RAZORPAY_KEY_ID='rzp_test_key'):
            body = client.get(reverse('student_dashboard')).content.decode()
        self.assertIn('Pay online', body)

    def test_dark_mode_toggle_can_be_switched_off(self):
        DashboardSettings.objects.update_or_create(
            pk=1, defaults={'show_dark_mode_toggle': False})
        body = self.login(self.data['mine']).get(reverse('student_dashboard')).content.decode()
        self.assertNotIn('id="dash-theme"', body)


class DashboardEmptyStateTests(TestCase):
    """A brand-new college has no subjects, no fees, no notices — must still work."""

    def test_dashboard_renders_for_a_student_with_no_data(self):
        lonely = make_student('stu-empty', 'EMPTY001', 'Empty Student', branch='', semester=None)
        client = Client(HTTP_HOST='localhost')
        client.force_login(lonely.user)
        response = client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('No subjects assigned yet', body)
        self.assertIn('No notices right now', body)
        self.assertIn('No events scheduled', body)
        self.assertIn('No result published yet', body)
        self.assertIn('0', body)          # fee due shows 0, not an error

    def test_no_dashboard_settings_row_is_fine(self):
        DashboardSettings.objects.all().delete()
        lonely = make_student('stu-nosettings', 'EMPTY002', 'No Settings')
        client = Client(HTTP_HOST='localhost')
        client.force_login(lonely.user)
        self.assertEqual(client.get(reverse('student_dashboard')).status_code, 200)
        self.assertTrue(DashboardSettings.objects.filter(pk=1).exists())


class DashboardQueryBudgetTests(TestCase):
    """One screen, one page: the dashboard must not scale queries with subjects."""

    @classmethod
    def setUpTestData(cls):
        cls.data = DashboardFixture.seed()

    def count_queries(self, subject_count):
        for index in range(subject_count):
            extra = Subject.objects.create(branch='CS', semester=3,
                                           subject_code=f'N{subject_count}{index:02d}',
                                           subject_name=f'Extra {subject_count}-{index}')
            Attendance.objects.create(student=self.data['mine'], subject=extra,
                                      date=timezone.localdate(), is_present=True)
            StudyMaterial.objects.create(title=f'Note {index}', subject=extra)
            ClassSchedule.objects.create(subject=extra, faculty=self.data['faculty'],
                                         weekday=timezone.localdate().weekday(),
                                         start_time=dt_time(11), end_time=dt_time(12))
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        with CaptureQueriesContext(connection) as captured:
            response = client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 200)
        return len(captured)

    def test_query_count_does_not_grow_with_subjects(self):
        small = self.count_queries(1)
        large = self.count_queries(15)   # +15 subjects, +15 schedules, +15 materials
        self.assertLessEqual(
            large - small, 2,
            f'dashboard queries grew from {small} to {large} when subjects were added '
            '(N+1 in the card data)')


class DashboardRequirementTests(TestCase):
    def setUp(self):
        self.out = StringIO()

    def test_seed_demo_still_builds_a_dashboard(self):
        """The demo seed is what a sales demo runs; the dashboard must render after it."""
        call_command('seed_demo', '--force', stdout=self.out)
        student = StudentProfile.objects.order_by('registration_number').first()
        client = Client(HTTP_HOST='localhost')
        client.force_login(student.user)
        response = client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('dash-grid', response.content.decode())


class DashboardCollegeIsolationTests(TestCase):
    """College B keeps its rows in its own database; A's dashboard must not show any.

    B's rows are given the same primary keys as A's, so "just change the id" is
    covered as well.
    """

    databases = {'default', 'college_b'}

    @classmethod
    def setUpTestData(cls):
        cls.mine = make_student('a-stu', 'AAAA0001', 'A College Student')
        subject = Subject.objects.create(branch='CS', semester=3, subject_code='CS301',
                                        subject_name='A College Subject')
        today = timezone.localdate()
        Attendance.objects.create(student=cls.mine, subject=subject, date=today, is_present=True)
        SemesterResult.objects.create(student=cls.mine, semester=3, subject=subject,
                                      total_marks=70, grade='B', is_pass=True)
        Notice.objects.create(title='A college notice', content='x')
        FeeStructure.objects.create(branch='CS', semester=3, fee_type='TUITION',
                                    amount=Decimal('1000'), academic_year='2024-2025')

        # College B: same table, other database, deliberately identical ids.
        b_user = User.objects.db_manager('college_b').create_user(
            username='b-stu', password='TestPass@12345')
        cls.b_student = StudentProfile.objects.using('college_b').create(
            pk=cls.mine.pk, user=b_user, name='B COLLEGE STUDENT', registration_number='BBBB0001',
            branch='CS', semester=3, year_of_admission=2023, is_password_changed=True)
        b_subject = Subject.objects.using('college_b').create(
            pk=subject.pk, branch='CS', semester=3, subject_code='CS301',
            subject_name='B COLLEGE SUBJECT')
        Attendance.objects.using('college_b').create(
            student=cls.b_student, subject=b_subject, date=today, is_present=False)
        SemesterResult.objects.using('college_b').create(
            student=cls.b_student, semester=3, subject=b_subject, total_marks=5,
            grade='F', is_pass=False)
        Notice.objects.using('college_b').create(title='B COLLEGE NOTICE', content='x')

    def test_dashboard_shows_only_this_deployments_rows(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.mine.user)
        body = client.get(reverse('student_dashboard')).content.decode()

        self.assertIn('A College Student', body)
        self.assertIn('A College Subject', body)
        self.assertIn('A college notice', body)

        for marker in ('B COLLEGE STUDENT', 'B COLLEGE SUBJECT', 'B COLLEGE NOTICE',
                       'BBBB0001', 'F</span>'):
            self.assertNotIn(marker, body)

    def test_marking_seen_only_touches_the_local_row(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.mine.user)
        client.get(reverse('student_dashboard'))

        self.assertIsNotNone(
            StudentProfile.objects.get(pk=self.mine.pk).dashboard_seen_at)
        self.assertIsNone(
            StudentProfile.objects.using('college_b').get(pk=self.mine.pk).dashboard_seen_at)


class DashboardA11yAndChromeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DashboardFixture.seed()

    def login(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        return client

    def test_single_h1_and_section_landmarks(self):
        body = self.login().get(reverse('student_dashboard')).content.decode()
        self.assertEqual(body.count('<h1'), 1, 'exactly one h1 per page')
        self.assertIn('aria-labelledby="h-courses"', body)
        self.assertIn('aria-current="page"', body)          # active sidebar item
        self.assertIn('<html lang=', body)
        self.assertIn('Skip to content', body)

    def test_unread_badge_has_a_text_alternative(self):
        body = self.login().get(reverse('student_dashboard')).content.decode()
        self.assertIn('aria-label="Notifications, 2 unread"', body)

    def test_dark_mode_is_applied_from_the_saved_cookie(self):
        client = self.login()
        client.cookies['ums_theme'] = 'dark'
        body = client.get(reverse('student_dashboard')).content.decode()
        # one dark-mode switch for every panel: data-theme on <html>
        self.assertIn('data-theme="dark"', body)

    def test_dashboard_assets_are_referenced_and_shipped(self):
        from pathlib import Path

        from django.conf import settings

        body = self.login().get(reverse('student_dashboard')).content.decode()
        self.assertIn('dashboard.css', body)
        self.assertIn('dashboard.js', body)
        self.assertTrue((Path(settings.BASE_DIR) / 'static/css/dashboard.css').exists())
        self.assertTrue((Path(settings.BASE_DIR) / 'static/js/dashboard.js').exists())
