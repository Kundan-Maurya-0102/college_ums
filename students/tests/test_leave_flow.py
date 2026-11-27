"""Leave application apply/approve/reject flow tests."""
import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from students.models import LeaveApplication, StudentProfile


class LeaveApplyTests(TestCase):
    """Student submits a leave application."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='leave_student', password='Str0ng!Pass1',
        )
        self.profile = StudentProfile.objects.create(
            user=self.user, name='Leave Student', phone='9876543210',
            registration_number='LV001', branch='CS', semester=1,
            is_password_changed=True,
        )
        self.client.force_login(self.user)

    def test_student_can_submit_leave(self):
        resp = self.client.post(reverse('student_leave_apply'), {
            'leave_type': 'SICK',
            'from_date': (datetime.date.today() + datetime.timedelta(days=1)).isoformat(),
            'to_date': (datetime.date.today() + datetime.timedelta(days=3)).isoformat(),
            'reason': 'Feeling unwell',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(LeaveApplication.objects.filter(student=self.profile).count(), 1)
        leave = LeaveApplication.objects.get(student=self.profile)
        self.assertEqual(leave.status, 'PENDING')
        self.assertEqual(leave.leave_type, 'SICK')

    def test_student_sees_own_leaves(self):
        LeaveApplication.objects.create(
            student=self.profile, leave_type='CASUAL',
            from_date=datetime.date.today(),
            to_date=datetime.date.today(),
            reason='Personal work',
        )
        resp = self.client.get(reverse('student_leave_apply'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Personal work')


class LeaveApproveRejectTests(TestCase):
    """Admin approves or rejects a leave application."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='leave_admin', password='Admin@12345', is_staff=True,
        )
        student_user = User.objects.create_user(username='leave_stu2')
        self.profile = StudentProfile.objects.create(
            user=student_user, name='Student 2', phone='9876543210',
            registration_number='LV002', branch='CS', semester=1,
        )
        self.leave = LeaveApplication.objects.create(
            student=self.profile, leave_type='FAMILY',
            from_date=datetime.date.today(),
            to_date=datetime.date.today() + datetime.timedelta(days=2),
            reason='Family emergency',
        )
        self.client.force_login(self.admin)

    def test_admin_can_approve_leave(self):
        resp = self.client.post(
            reverse('leave_review', args=[self.leave.pk]),
            {'action': 'APPROVED', 'remarks': 'Approved by admin'},
        )
        self.assertEqual(resp.status_code, 302)
        self.leave.refresh_from_db()
        self.assertEqual(self.leave.status, 'APPROVED')
        self.assertEqual(self.leave.reviewed_by, self.admin)
        self.assertIsNotNone(self.leave.reviewed_at)

    def test_admin_can_reject_leave(self):
        resp = self.client.post(
            reverse('leave_review', args=[self.leave.pk]),
            {'action': 'REJECTED', 'remarks': 'Not approved'},
        )
        self.assertEqual(resp.status_code, 302)
        self.leave.refresh_from_db()
        self.assertEqual(self.leave.status, 'REJECTED')

    def test_admin_sees_leave_list(self):
        resp = self.client.get(reverse('leave_applications'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Family emergency')

    def test_invalid_action_does_not_change_status(self):
        resp = self.client.post(
            reverse('leave_review', args=[self.leave.pk]),
            {'action': 'INVALID_ACTION', 'remarks': ''},
        )
        self.assertEqual(resp.status_code, 302)
        self.leave.refresh_from_db()
        self.assertEqual(self.leave.status, 'PENDING')
