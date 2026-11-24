"""Performance guardrails: query-count budgets for the hot pages.

These fail if someone reintroduces an N+1 loop. Budgets are generous
(page-render queries on a small dataset), tight enough to catch 2x regressions.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from students.models import StudentProfile, Subject


class QueryBudgetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("perf_admin", password="TestPass!2345", is_staff=True)
        cls.teacher_user = User.objects.create_user("perf_teacher", password="TestPass!2345",
                                                    is_staff=True)
        from students.models import FacultyProfile

        FacultyProfile.objects.create(user=cls.teacher_user, name="Perf Teacher")
        Subject.objects.create(branch="CS", semester=1, subject_code="PF101", subject_name="Perf")
        for i in range(25):
            user = User.objects.create_user(f"perf_student_{i}", password="TestPass!2345")
            StudentProfile.objects.create(user=user, name=f"Perf Student {i}",
                                          registration_number=f"PF{i:03d}",
                                          branch="CS", semester=1)

    def _queries(self, url_name, user, budget):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_login(user)
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse(url_name))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(
            len(ctx), budget,
            f"{url_name} ran {len(ctx)} queries (budget {budget}) — N+1 regression?")

    def test_student_list_stays_within_budget(self):
        self._queries("student_list", self.admin, 8)

    def test_fee_payments_within_budget(self):
        self._queries("fee_payments", self.admin, 8)

    def test_reports_within_budget(self):
        self._queries("reports_view", self.admin, 20)

    def test_teacher_students_within_budget(self):
        self._queries("teacher_students", self.teacher_user, 9)

    def test_pagination_is_applied_to_large_lists(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("student_list"))
        self.assertTrue(response.context["page_obj"].paginator.num_pages >= 2)
        self.assertLessEqual(len(response.context["page_obj"].object_list), 20)

    def test_dashboard_visit_stats_use_one_aggregate(self):
        """The dashboard must not run one query per visit metric."""
        from students.models import WebsiteVisit
        from django.utils import timezone

        for _ in range(5):
            WebsiteVisit.objects.create(path="/", visited_at=timezone.now())

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_login(self.admin)
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(reverse("admin_dashboard"))
        self.assertLessEqual(len(ctx), 18, "admin dashboard query count regressed")
