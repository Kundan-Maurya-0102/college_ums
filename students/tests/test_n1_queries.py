"""N+1 query budget tests for dashboards.

These tests set an upper bound on the number of queries each dashboard
executes so a future ORM change that adds per-row queries breaks CI.
"""
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from students.models import (
    FacultyProfile,
    StudentProfile,
    Subject,
)


class StudentDashboardQueryBudgetTests(TestCase):
    """Student dashboard must stay within a fixed query budget."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='qdash_student', password='Str0ng!Pass1',
        )
        self.profile = StudentProfile.objects.create(
            user=self.user, name='Query Student', phone='9876543210',
            registration_number='QD001', branch='CS', semester=1,
            is_password_changed=True,
        )
        for i in range(4):
            Subject.objects.create(
                subject_code=f'QCS{i}', subject_name=f'Subject {i}',
                branch='CS', semester=1,
            )

    def test_student_dashboard_query_count(self):
        self.client.force_login(self.user)
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get('/dashboard/')
        self.assertEqual(resp.status_code, 200)
        # Budget: session + user + profile + dashboard_data queries.
        # Allow headroom but catch N+1 regressions.
        self.assertLessEqual(
            len(ctx), 35,
            f"Student dashboard ran {len(ctx)} queries (budget 35):\n"
            + "\n".join(q['sql'][:120] for q in ctx),
        )


class TeacherDashboardQueryBudgetTests(TestCase):
    """Teacher dashboard must stay within a fixed query budget."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='qdash_teacher', password='Str0ng!Pass1', is_staff=True,
        )
        self.faculty = FacultyProfile.objects.create(
            user=self.user, name='Query Teacher', phone='9876543210',
            department='CS',
        )
        for i in range(4):
            subj = Subject.objects.create(
                subject_code=f'QTS{i}', subject_name=f'T Subject {i}',
                branch='CS', semester=1,
            )
            self.faculty.subjects.add(subj)

    def test_teacher_dashboard_query_count(self):
        self.client.force_login(self.user)
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get('/teacher/')
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(
            len(ctx), 35,
            f"Teacher dashboard ran {len(ctx)} queries (budget 35):\n"
            + "\n".join(q['sql'][:120] for q in ctx),
        )


class AdminDashboardQueryBudgetTests(TestCase):
    """Admin dashboard must stay within a fixed query budget."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='qdash_admin', password='Str0ng!Pass1', is_staff=True,
        )

    def test_admin_dashboard_query_count(self):
        self.client.force_login(self.user)
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get('/admin-panel/')
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(
            len(ctx), 35,
            f"Admin dashboard ran {len(ctx)} queries (budget 35):\n"
            + "\n".join(q['sql'][:120] for q in ctx),
        )
