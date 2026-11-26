"""Admin panel: role-gated navigation, aggregate dashboard and no cross-college rows."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from students.models import (
    Attendance,
    AuditLog,
    FacultyProfile,
    FeePayment,
    FeeStructure,
    LeaveApplication,
    Notice,
    StudentProfile,
    Subject,
)

User = get_user_model()


def make_admin(username='office', superuser=False):
    return User.objects.create_user(username=username, password='TestPass@12345',
                                    is_staff=True, is_superuser=superuser)


def make_student(username, reg, name, branch='CS', semester=3):
    user = User.objects.create_user(username=username, password='TestPass@12345')
    return StudentProfile.objects.create(user=user, name=name, registration_number=reg,
                                         branch=branch, semester=semester,
                                         year_of_admission=2023, is_password_changed=True)


class AdminDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()
        cls.teacher = User.objects.create_user('t1', password='TestPass@12345', is_staff=True)
        FacultyProfile.objects.create(user=cls.teacher, name='Teacher One', department='CS')
        cls.student = make_student('s1', 'ADM001', 'Admin Student')
        cls.subject = Subject.objects.create(branch='CS', semester=3, subject_code='CS301',
                                             subject_name='Database Systems')
        today = timezone.localdate()
        Attendance.objects.create(student=cls.student, subject=cls.subject,
                                  date=today, is_present=False)
        structure = FeeStructure.objects.create(branch='CS', semester=3, fee_type='TUITION',
                                                amount=Decimal('40000'),
                                                academic_year='2025-2026')
        FeePayment.objects.create(student=cls.student, fee_structure=structure,
                                  amount_paid=Decimal('10000'), payment_date=today,
                                  receipt_number='R-1', status='PARTIAL')
        LeaveApplication.objects.create(student=cls.student, leave_type='SICK',
                                        from_date=today, to_date=today, reason='x')
        Notice.objects.create(title='Notice', content='x')
        AuditLog.objects.create(user=cls.admin, action='update', model_name='StudentProfile',
                                object_id=str(cls.student.pk), detail='phone')

    def login(self, user=None):
        client = Client(HTTP_HOST='localhost')
        client.force_login(user or self.admin)
        return client

    def test_dashboard_renders_with_cards_and_charts(self):
        response = self.login().get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin_dashboard/shell.html')
        self.assertEqual(len(response.context['stat_cards']), 6)
        self.assertEqual(response.context['charts']['branches'][0]['label'], 'Computer Science')
        self.assertEqual(response.context['charts']['pass_rate'], None)
        self.assertTrue(response.context['activity'])

    def test_stat_card_numbers_match_the_database(self):
        cards = {card['key']: card['value']
                 for card in self.login().get(reverse('admin_dashboard')).context['stat_cards']}
        self.assertEqual(cards['students'], 1)
        self.assertEqual(cards['teachers'], 1)
        self.assertEqual(cards['attendance'], '0.0%')
        self.assertEqual(cards['leave'], 1)

    def test_attention_panel_lists_the_low_attendance_student(self):
        attention = self.login().get(reverse('admin_dashboard')).context['attention']
        self.assertEqual([row['student'].registration_number for row in attention['low_attendance']],
                         ['ADM001'])
        self.assertEqual(attention['pending_leave'], 1)

    def test_dashboard_query_count_is_flat(self):
        client = self.login()

        def count():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(client.get(reverse('admin_dashboard')).status_code, 200)
            return len(ctx.captured_queries)

        before = count()
        for i in range(10):
            student = make_student(f'bulk{i}', f'B{i:03d}', f'Bulk {i}')
            Attendance.objects.create(student=student, subject=self.subject,
                                      date=timezone.localdate() - timedelta(days=1),
                                      is_present=i % 2 == 0)
        after = count()
        self.assertLessEqual(after, before + 2, f'{before} -> {after} with 10 more students')

    def test_teacher_cannot_open_the_admin_dashboard(self):
        response = self.login(self.teacher).get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_student_cannot_open_the_admin_dashboard(self):
        response = self.login(self.student.user).get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)


class AdminNavigationTests(TestCase):
    """A role only sees the menu entries it can actually open."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin()

    def body(self, user=None):
        client = Client(HTTP_HOST='localhost')
        client.force_login(user or self.admin)
        return client.get(reverse('admin_dashboard')).content.decode()

    def test_admin_sees_grouped_sidebar_sections(self):
        body = self.body()
        for group in ('Students', 'Staff', 'Academics', 'Money', 'Communication',
                      'Reports', 'System'):
            with self.subTest(group=group):
                self.assertIn(group, body)

    def test_admin_links_resolve(self):
        from django.urls import reverse as r
        body = self.body()
        for name in ('student_list', 'teacher_list', 'subject_list', 'fee_payments',
                     'notice_list', 'reports_view', 'system_status', 'leave_applications',
                     'admin_exam_documents'):
            with self.subTest(link=name):
                self.assertIn(r(name), body)

    def test_no_student_only_or_superadmin_only_links(self):
        body = self.body()
        from django.urls import reverse as r
        for name in ('student_dashboard', 'student_fees', 'student_leave_apply'):
            with self.subTest(link=name):
                self.assertNotIn(r(name), body)


class AdminCrossCollegeTests(TestCase):
    """Everything the dashboard counts is from this deployment's database only."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_admin('office2')
        cls.mine = make_student('x1', 'X001', 'Mine Only', 'CS', 3)
        cls.other_branch = make_student('x2', 'X002', 'Other Branch', 'ME', 5)

    def test_branch_chart_only_contains_this_database(self):
        charts = Client(HTTP_HOST='localhost')
        charts.force_login(self.admin)
        response = charts.get(reverse('admin_dashboard'))
        labels = [row['label'] for row in response.context['charts']['branches']]
        self.assertEqual(sorted(labels), ['Computer Science', 'Mechanical'])
        self.assertEqual(response.context['stat_cards'][0]['value'], 2)

    def test_activity_feed_only_shows_local_rows(self):
        AuditLog.objects.create(user=self.admin, action='create',
                                model_name='StudentProfile', object_id='9', detail='local')
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.admin)
        rows = client.get(reverse('admin_dashboard')).context['activity']
        self.assertEqual([row['log'].detail for row in rows], ['local'])
