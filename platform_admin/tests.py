"""Super-admin (platform owner) panel: permissions, lifecycle, tickets, metrics."""
import json
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from platform_admin.models import (
    College,
    Plan,
    SupportTicket,
    TicketReply,
    UsageSnapshot,
    platform_admin_required,
)

PASSWORD = "TestPass!2345"


def make_user(username, **kwargs):
    return User.objects.create_user(username, password=PASSWORD, **kwargs)


class PlatformFixtures(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = make_user("platform_root", is_superuser=True, is_staff=True)
        cls.group_user = make_user("platform_agent", is_staff=True)
        group, _ = Group.objects.get_or_create(name="Platform Admin")
        cls.group_user.groups.add(group)
        cls.college_admin = make_user("college_admin_x", is_staff=True)
        cls.student_user = make_user("college_student_x")

        cls.plan = Plan.objects.create(name="Pro", code="pro", price_monthly=4999,
                                       student_limit=2000,
                                       features=["fees", "reports", "whatsapp"])
        cls.college = College.objects.create(
            name="Test Polytechnic", slug="test-poly", domain="ums.test.edu",
            plan=cls.plan, status=College.STATUS_ACTIVE,
            subscription_expires_on=timezone.localdate() + timedelta(days=90),
            student_count=120, active_users_30d=45, storage_bytes=5 * 1024 * 1024,
            contact_email="office@test.edu")

    def login(self, user):
        client = Client(HTTP_HOST="localhost")
        client.force_login(user)
        return client


class PlatformAccessTests(PlatformFixtures):
    def test_superuser_can_open_panel(self):
        response = self.login(self.superuser).get("/platform/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Platform overview")

    def test_group_member_can_open_panel(self):
        self.assertEqual(self.login(self.group_user).get("/platform/").status_code, 200)

    def test_college_staff_is_forbidden(self):
        for url in ("/platform/", "/platform/colleges/", "/platform/plans/",
                    "/platform/usage/", "/platform/tickets/"):
            with self.subTest(url=url):
                self.assertEqual(self.login(self.college_admin).get(url).status_code, 403)

    def test_student_is_forbidden(self):
        self.assertEqual(self.login(self.student_user).get("/platform/colleges/").status_code, 403)

    def test_anonymous_redirected_to_login(self):
        response = Client(HTTP_HOST="localhost").get("/platform/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_platform_admin_helper(self):
        self.assertTrue(platform_admin_required(self.superuser))
        self.assertTrue(platform_admin_required(self.group_user))
        self.assertFalse(platform_admin_required(self.college_admin))
        self.assertFalse(platform_admin_required(self.student_user))


class CollegeListTests(PlatformFixtures):
    def test_list_shows_metrics(self):
        College.objects.create(name="Second College", slug="second", student_count=7)
        response = self.login(self.superuser).get("/platform/colleges/")
        self.assertContains(response, "Test Polytechnic")
        self.assertContains(response, "Second College")
        self.assertContains(response, "120 / 2000")
        self.assertContains(response, "5.0 MB")

    def test_search_and_status_filter(self):
        College.objects.create(name="Suspended College", slug="susp", student_count=3,
                               status=College.STATUS_SUSPENDED)
        client = self.login(self.superuser)
        self.assertContains(client.get("/platform/colleges/?q=susp"), "Suspended College")
        response = client.get("/platform/colleges/?status=suspended")
        self.assertContains(response, "Suspended College")
        self.assertNotContains(response, "Test Polytechnic")

    def test_pagination_applies(self):
        for i in range(25):
            College.objects.create(name=f"Bulk College {i}", slug=f"bulk-{i}")
        response = self.login(self.superuser).get("/platform/colleges/")
        self.assertLessEqual(len(response.context["page_obj"].object_list), 20)
        self.assertGreaterEqual(response.context["page_obj"].paginator.num_pages, 2)


class SubscriptionTests(PlatformFixtures):
    def test_suspend_and_resume(self):
        client = self.login(self.superuser)
        response = client.post(f"/platform/colleges/{self.college.pk}/suspend/", follow=True)
        self.assertContains(response, "suspended")
        self.college.refresh_from_db()
        self.assertEqual(self.college.status, College.STATUS_SUSPENDED)
        self.assertTrue(self.college.is_read_only)

        client.post(f"/platform/colleges/{self.college.pk}/resume/")
        self.college.refresh_from_db()
        self.assertEqual(self.college.status, College.STATUS_ACTIVE)
        self.assertFalse(self.college.is_read_only)

    def test_expired_subscription_is_read_only(self):
        self.college.subscription_expires_on = timezone.localdate() - timedelta(days=1)
        self.college.save()
        self.assertTrue(self.college.is_expired)
        self.assertTrue(self.college.is_read_only)

    def test_resume_of_expired_college_returns_expired_status(self):
        self.college.subscription_expires_on = timezone.localdate() - timedelta(days=1)
        self.college.status = College.STATUS_SUSPENDED
        self.college.save()
        client = self.login(self.superuser)
        client.post(f"/platform/colleges/{self.college.pk}/resume/")
        self.college.refresh_from_db()
        self.assertEqual(self.college.status, College.STATUS_EXPIRED)

    def test_suspend_requires_post(self):
        response = self.login(self.superuser).get(f"/platform/colleges/{self.college.pk}/suspend/")
        self.assertEqual(response.status_code, 403)

    def test_effective_limit_falls_back_to_plan(self):
        self.assertEqual(self.college.effective_limit, 2000)
        self.college.student_limit = 300
        self.college.save()
        self.assertEqual(self.college.effective_limit, 300)

    @override_settings(COLLEGE_SLUG="test-poly")
    def test_middleware_blocks_writes_for_suspended_college(self):
        self.college.status = College.STATUS_SUSPENDED
        self.college.save()
        from django.core.cache import cache

        cache.clear()
        client = self.login(self.student_user)
        response = client.post("/forum/", {})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "read-only", status_code=403)

    @override_settings(COLLEGE_SLUG="test-poly")
    def test_middleware_lets_reads_through_when_suspended(self):
        self.college.status = College.STATUS_SUSPENDED
        self.college.save()
        from django.core.cache import cache

        cache.clear()
        response = self.login(self.student_user).get("/privacy/")
        self.assertEqual(response.status_code, 200)


class BackupDownloadTests(PlatformFixtures):
    @override_settings(PLATFORM_BACKUP_DIR="/var/backups/ums-nonexistent")
    def test_snapshot_download_is_json_and_audited(self):
        from students.models import AuditLog

        response = self.login(self.superuser).get(
            f"/platform/colleges/{self.college.pk}/backup/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        payload = json.loads(response.content)
        self.assertEqual(payload["college"]["slug"], "test-poly")
        self.assertEqual(payload["metrics"]["student_count"], 120)
        self.assertTrue(AuditLog.objects.filter(action="platform.college.backup_download").exists())

    def test_backup_path_outside_allowed_dir_is_not_served(self):
        self.college.backup_path = "/etc/passwd"
        self.college.save()
        response = self.login(self.superuser).get(
            f"/platform/colleges/{self.college.pk}/backup/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"root:", response.content)


class PlanTests(PlatformFixtures):
    def test_plan_list_and_feature_flags(self):
        response = self.login(self.superuser).get("/platform/plans/")
        self.assertContains(response, "Pro")
        self.assertContains(response, "fees")

    def test_create_plan_rejects_unknown_module(self):
        client = self.login(self.superuser)
        response = client.post("/platform/plans/new/", {
            "name": "Cheap", "code": "cheap", "price_monthly": "99", "student_limit": "100",
            "features": '["fees", "teleportation"]', "is_active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unknown modules")

    def test_has_feature_gate(self):
        self.assertTrue(self.college.has_feature("fees"))
        self.assertFalse(self.college.has_feature("ai_chatbot"))


class TicketTests(PlatformFixtures):
    def test_ticket_lifecycle(self):
        client = self.login(self.superuser)
        response = client.post("/platform/tickets/new/", {
            "college": self.college.pk, "subject": "Fee report broken",
            "body": "Reports page 500s", "opened_by": "college admin",
            "priority": "high",
        }, follow=True)
        ticket = SupportTicket.objects.get()
        self.assertEqual(ticket.status, SupportTicket.STATUS_OPEN)
        self.assertContains(response, "Fee report broken")

        response = client.post(f"/platform/tickets/{ticket.pk}/", {"body": "Fixed in v2."},
                               follow=True)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, SupportTicket.STATUS_ANSWERED)
        self.assertEqual(TicketReply.objects.filter(ticket=ticket).count(), 1)
        self.assertContains(response, "Fixed in v2.")

        client.post(f"/platform/tickets/{ticket.pk}/", {"action": "close"})
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, SupportTicket.STATUS_CLOSED)

    def test_ticket_filter_by_status(self):
        SupportTicket.objects.create(college=self.college, subject="Open one", body="x")
        SupportTicket.objects.create(college=self.college, subject="Closed one", body="y",
                                     status=SupportTicket.STATUS_CLOSED)
        response = self.login(self.superuser).get("/platform/tickets/?status=closed")
        self.assertContains(response, "Closed one")
        self.assertNotContains(response, "Open one")


class UsageTests(PlatformFixtures):
    def test_usage_page_totals_and_csv(self):
        client = self.login(self.superuser)
        response = client.get("/platform/usage/")
        self.assertEqual(response.context["totals"]["students"], 120)
        csv_response = client.get("/platform/usage/?format=csv")
        self.assertEqual(csv_response["Content-Type"], "text/csv")
        body = csv_response.content.decode()
        self.assertIn("test-poly", body)
        self.assertIn("students", body.splitlines()[0])

    def test_overview_counts(self):
        College.objects.create(name="Trial College", slug="trial-one",
                               status=College.STATUS_TRIAL)
        SupportTicket.objects.create(college=self.college, subject="Help", body="x")
        response = self.login(self.superuser).get("/platform/")
        self.assertEqual(response.context["stats"]["colleges"], 2)
        self.assertEqual(response.context["stats"]["trial"], 1)
        self.assertEqual(response.context["stats"]["open_tickets"], 1)


class MetricsEndpointTests(PlatformFixtures):
    @override_settings(PLATFORM_METRICS_TOKEN="secret-token")
    def test_valid_report_updates_college_and_snapshot(self):
        response = self.client.post(
            "/platform/metrics/test-poly/",
            data=json.dumps({"student_count": 555, "active_users_30d": 99,
                             "storage_bytes": 1048576 * 2, "messages_sent": 12,
                             "payments_count": 3, "api_calls": 40}),
            content_type="application/json", HTTP_X_PLATFORM_TOKEN="secret-token",
            HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.college.refresh_from_db()
        self.assertEqual(self.college.student_count, 555)
        self.assertEqual(self.college.storage_bytes, 2097152)
        self.assertIsNotNone(self.college.metrics_reported_at)
        snapshot = UsageSnapshot.objects.get(college=self.college,
                                             day=timezone.localdate())
        self.assertEqual(snapshot.messages_sent, 12)
        self.assertEqual(snapshot.payments_count, 3)

    @override_settings(PLATFORM_METRICS_TOKEN="secret-token")
    def test_bad_token_rejected(self):
        response = self.client.post("/platform/metrics/test-poly/", data="{}",
                                    content_type="application/json",
                                    HTTP_X_PLATFORM_TOKEN="wrong", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 403)

    @override_settings(PLATFORM_METRICS_TOKEN="")
    def test_endpoint_disabled_without_token(self):
        response = self.client.post("/platform/metrics/test-poly/", data="{}",
                                    content_type="application/json",
                                    HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 403)

    @override_settings(PLATFORM_METRICS_TOKEN="secret-token")
    def test_invalid_json_rejected(self):
        response = self.client.post("/platform/metrics/test-poly/", data="not json",
                                    content_type="application/json",
                                    HTTP_X_PLATFORM_TOKEN="secret-token",
                                    HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 400)


class CommandTests(PlatformFixtures):
    def test_seed_plans_is_idempotent(self):
        from django.core.management import call_command

        call_command("seed_plans", verbosity=0)
        call_command("seed_plans", verbosity=0)
        self.assertEqual(Plan.objects.filter(code="basic").count(), 1)

    def test_reminders_dry_run_then_apply(self):
        from io import StringIO

        from django.core import mail
        from django.core.management import call_command

        self.college.subscription_expires_on = date.today() + timedelta(days=3)
        self.college.save()

        out = StringIO()
        call_command("send_subscription_reminders", stdout=out)
        self.assertIn("expires in 3 day(s)", out.getvalue())
        self.assertEqual(len(mail.outbox), 0)

        # run the queued job inline instead of waiting for a worker
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"), \
                patch("django_q.tasks.async_task",
                      side_effect=lambda func, *a, **kw: func(*a, **kw)):
            call_command("send_subscription_reminders", "--apply", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Subscription", mail.outbox[0].subject)

    def test_report_metrics_dry_run(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        with override_settings(COLLEGE_SLUG="test-poly"):
            call_command("report_college_metrics", "--dry-run", stdout=out)
        self.assertIn("student_count", out.getvalue())


class MetricsEndpointIsMachineCallableTests(TestCase):
    """The token API must work without a browser session or CSRF cookie."""

    def setUp(self):
        self.college = College.objects.create(
            name='Machine College', slug='machine-college', metrics_token='machine-token')

    def test_post_without_csrf_token_succeeds(self):
        client = Client(enforce_csrf_checks=True, HTTP_HOST='localhost')
        response = client.post(
            reverse('platform_metrics', args=['machine-college']),
            data=json.dumps({'student_count': 12}),
            content_type='application/json',
            HTTP_X_PLATFORM_TOKEN='machine-token')
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.college.refresh_from_db()
        self.assertEqual(self.college.student_count, 12)

    def test_wrong_token_is_still_rejected_without_csrf(self):
        client = Client(enforce_csrf_checks=True, HTTP_HOST='localhost')
        response = client.post(
            reverse('platform_metrics', args=['machine-college']),
            data=json.dumps({'student_count': 99}),
            content_type='application/json',
            HTTP_X_PLATFORM_TOKEN='nope')
        self.assertEqual(response.status_code, 403)
