"""Parent / guardian portal: read-only, and only their own children."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from students.models import (
    Attendance,
    GuardianProfile,
    InternalExam,
    StudentProfile,
    Subject,
)

User = get_user_model()


def make_student(reg, name):
    user = User.objects.create_user(username=reg.lower(), password='TestPass@12345')
    return StudentProfile.objects.create(
        user=user, name=name, registration_number=reg, branch='CS', semester=3,
        year_of_admission=2023, is_password_changed=True)


class GuardianPortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.child = make_student('P001', 'Child One')
        cls.other = make_student('P002', 'Other Child')
        subject = Subject.objects.create(
            branch='CS', semester=3, subject_code='CS301', subject_name='DBMS')
        Attendance.objects.create(student=cls.child, subject=subject,
                                  date=timezone.localdate(), is_present=True)
        InternalExam.objects.create(student=cls.child, subject=subject, exam_type='MSE',
                                    marks_obtained=40, max_marks=50,
                                    exam_date=timezone.localdate())
        cls.parent_user = User.objects.create_user(username='parent1', password='TestPass@12345')
        cls.guardian = GuardianProfile.objects.create(
            user=cls.parent_user, name='Parent One', phone='9876543210')
        cls.guardian.students.add(cls.child)

        cls.other_parent_user = User.objects.create_user(
            username='parent2', password='TestPass@12345')
        cls.other_guardian = GuardianProfile.objects.create(
            user=cls.other_parent_user, name='Parent Two')
        cls.other_guardian.students.add(cls.other)

    def login_parent(self, user=None):
        client = Client(HTTP_HOST='localhost')
        client.force_login(user or self.parent_user)
        return client

    def test_dashboard_lists_own_child_only(self):
        response = self.login_parent().get(reverse('parent_dashboard'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('Child One', body)
        self.assertNotIn('Other Child', body)

    def test_child_detail_shows_marks_and_attendance(self):
        response = self.login_parent().get(
            reverse('parent_child', args=[self.child.pk]))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('DBMS', body)
        self.assertIn('40/50', body)
        self.assertIn('100.0%', body)

    def test_other_families_child_is_404(self):
        response = self.login_parent().get(
            reverse('parent_child', args=[self.other.pk]))
        self.assertEqual(response.status_code, 404)

    def test_portal_is_read_only(self):
        client = self.login_parent()
        for url in (reverse('parent_dashboard'), reverse('parent_child', args=[self.child.pk])):
            self.assertEqual(client.post(url, {'x': '1'}).status_code, 405)

    def test_anonymous_is_redirected_to_login(self):
        response = Client(HTTP_HOST='localhost').get(reverse('parent_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_user_without_guardian_profile_is_sent_away(self):
        stranger = User.objects.create_user(username='stranger', password='TestPass@12345')
        response = self.login_parent(stranger).get(reverse('parent_dashboard'), follow=True)
        self.assertRedirects(response, reverse('student_login'))

    def test_login_lands_on_parent_dashboard(self):
        client = Client(HTTP_HOST='localhost')
        response = client.post(reverse('student_login'),
                               {'username': 'parent1', 'password': 'TestPass@12345'})
        self.assertRedirects(response, reverse('parent_dashboard'))

    def test_guardian_cannot_reach_staff_areas(self):
        client = self.login_parent()
        for name in ('admin_dashboard', 'teacher_dashboard', 'student_dashboard',
                     'student_list', 'export_students_csv'):
            response = client.get(reverse(name))
            self.assertIn(response.status_code, (302, 403, 404), name)

    def test_guardian_cannot_read_staff_only_media(self):
        import shutil
        import tempfile
        from pathlib import Path

        from django.test import override_settings

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / 'csv_uploads').mkdir()
        (tmp / 'csv_uploads' / 'students.csv').write_text('reg\n')
        with override_settings(MEDIA_ROOT=tmp, MEDIA_PROTECTED=True):
            response = self.login_parent().get('/media/csv_uploads/students.csv')
        self.assertEqual(response.status_code, 404)

    def test_inactive_guardian_loses_access(self):
        self.guardian.is_active = False
        self.guardian.save(update_fields=['is_active'])
        response = self.login_parent().get(reverse('parent_dashboard'), follow=True)
        self.assertRedirects(response, reverse('student_login'))


class AddGuardianCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.child = make_student('P010', 'Child Ten')
        cls.child2 = make_student('P011', 'Child Eleven')

    def run_command(self, *args):
        out = StringIO()
        call_command('add_guardian', *args, stdout=out)
        return out.getvalue()

    def test_creates_account_and_prints_set_password_link(self):
        text = self.run_command('--student', 'P010', '--name', 'Guardian Ten',
                                '--phone', '9876500011')
        self.assertIn('/set-password/', text)
        guardian = GuardianProfile.objects.get(name='Guardian Ten')
        self.assertEqual(guardian.user.username, '9876500011')
        self.assertFalse(guardian.user.has_usable_password())
        self.assertEqual(list(guardian.students.all()), [self.child])

    def test_links_siblings_to_one_account(self):
        self.run_command('--student', 'P010', '--student', 'P011',
                         '--name', 'Guardian Siblings', '--username', 'siblings')
        guardian = GuardianProfile.objects.get(user__username='siblings')
        self.assertEqual(guardian.students.count(), 2)

    def test_unknown_registration_number_fails_clearly(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as ctx:
            self.run_command('--student', 'NOPE', '--name', 'X')
        self.assertIn('NOPE', str(ctx.exception))

    def test_dry_run_writes_nothing(self):
        text = self.run_command('--student', 'P010', '--name', 'Dry Run', '--dry-run')
        self.assertIn('dry run', text)
        self.assertFalse(GuardianProfile.objects.filter(name='Dry Run').exists())

    def test_rerun_reactivates_the_same_guardian(self):
        self.run_command('--student', 'P010', '--name', 'G One', '--username', 'gone')
        GuardianProfile.objects.filter(user__username='gone').update(is_active=False)
        self.run_command('--student', 'P011', '--name', 'G One', '--username', 'gone')
        guardian = GuardianProfile.objects.get(user__username='gone')
        self.assertTrue(guardian.is_active)
        self.assertEqual(guardian.students.count(), 2)
