"""Demo seeding, public landing page + demo requests, in-app bug reporting."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from platform_admin.models import DemoRequest, Plan
from students.models import (
    Attendance,
    BugReport,
    FeePayment,
    InternalExam,
    Notice,
    StudentProfile,
    Subject,
)

User = get_user_model()
DEMO_PASS = 'Demo@12345'


class DemoSeedTests(TestCase):
    def _seed(self, *args):
        out = StringIO()
        call_command('seed_demo', '--students', '6', '--teachers', '2', '--force',
                     *args, stdout=out)
        return out.getvalue()

    def test_seed_creates_a_usable_college(self):
        self._seed()
        self.assertEqual(User.objects.filter(username__startswith='demo_student').count(), 6)
        self.assertEqual(User.objects.filter(username__startswith='demo_teacher').count(), 2)
        self.assertTrue(Subject.objects.exists())
        self.assertTrue(Attendance.objects.exists())
        self.assertTrue(InternalExam.objects.exists())
        self.assertTrue(FeePayment.objects.exists())
        self.assertTrue(Notice.objects.filter(title__startswith='[Demo]').exists())

    def test_demo_accounts_can_log_in_and_browse(self):
        self._seed()
        self.assertTrue(self.client.login(username='demo_student1', password=DEMO_PASS))
        for url in ('/dashboard/', '/my-fees/', '/exam-schedule/', '/events/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_demo_teacher_can_open_teaching_pages(self):
        self._seed()
        self.assertTrue(self.client.login(username='demo_teacher1', password=DEMO_PASS))
        for url in ('/teacher/', '/teacher/students/', '/teacher/marks/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_seed_is_idempotent(self):
        self._seed()
        counts = (StudentProfile.objects.count(), Attendance.objects.count(),
                  FeePayment.objects.count())
        self._seed()
        self.assertEqual(
            (StudentProfile.objects.count(), Attendance.objects.count(),
             FeePayment.objects.count()), counts)

    def test_flush_removes_previous_demo_rows(self):
        self._seed()
        self._seed('--flush')
        self.assertEqual(User.objects.filter(username='demo_student1').count(), 1)

    @override_settings(DEBUG=False)
    def test_refuses_to_seed_when_debug_is_off(self):
        with self.assertRaises(CommandError):
            call_command('seed_demo', '--students', '2', '--teachers', '1', stdout=StringIO())


@override_settings(LANDING_PAGE_ENABLED=True)
class LandingPageTests(TestCase):
    def setUp(self):
        Plan.objects.create(name='Basic', code='basic', price_monthly=5000,
                            student_limit=500, features=['students', 'fees'])

    def test_anonymous_visitor_sees_features_pricing_and_form(self):
        body = self.client.get('/').content.decode()
        self.assertIn('Book a demo', body)
        self.assertIn('Pricing', body)
        self.assertIn('5,000', body.replace('5000', '5,000'))
        self.assertIn('name="college_name"', body)
        # module codes must be shown as human labels
        self.assertIn('Student records &amp; import', body)

    def test_demo_request_is_stored(self):
        response = self.client.post('/', {
            'college_name': 'Govt Polytechnic Gaya',
            'contact_name': 'Ramesh Kumar',
            'email': 'principal@gpgaya.ac.in',
            'phone': '98765 43210',
            'students': '480',
            'message': 'We want a demo next week.',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Thank you')
        lead = DemoRequest.objects.get()
        self.assertEqual(lead.phone, '9876543210')      # digits only
        self.assertEqual(lead.status, 'NEW')
        self.assertEqual(lead.source, 'landing')

    def test_invalid_demo_request_shows_errors(self):
        response = self.client.post('/', {
            'college_name': 'X', 'contact_name': '', 'email': 'not-an-email', 'phone': '12',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errorlist')
        self.assertEqual(DemoRequest.objects.count(), 0)

    def test_signed_in_user_is_redirected_to_their_panel(self):
        User.objects.create_user('landingadmin', password='Xyz@12345',
                                 is_staff=True, is_superuser=True)
        self.client.login(username='landingadmin', password='Xyz@12345')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin-panel/', response['Location'])

    @override_settings(LANDING_PAGE_ENABLED=False)
    def test_landing_can_be_switched_off(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])


class BugReportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('reporter', password='Xyz@12345')
        StudentProfile.objects.create(user=self.user, name='Reporter', registration_number='R001',
                                      branch='CS', semester=1, year_of_admission=2024,
                                      is_password_changed=True)
        self.client.login(username='reporter', password='Xyz@12345')

    def test_report_is_saved_with_context(self):
        response = self.client.post('/report-problem/', {
            'category': 'BUG',
            'message': 'The fee page went blank after I pressed save.',
            'page_url': '/my-fees/',
            'next': '/my-fees/',
        })
        self.assertEqual(response.status_code, 302)
        report = BugReport.objects.get()
        self.assertEqual(report.user, self.user)
        self.assertEqual(report.role, 'student')
        self.assertEqual(report.page_url, '/my-fees/')
        self.assertEqual(report.status, 'OPEN')

    def test_too_short_message_is_rejected(self):
        self.client.post('/report-problem/', {'category': 'BUG', 'message': 'broken'})
        self.assertEqual(BugReport.objects.count(), 0)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get('/report-problem/').status_code, 405)

    def test_anonymous_user_cannot_report(self):
        self.client.logout()
        response = self.client.post('/report-problem/', {'category': 'BUG',
                                                         'message': 'spam spam spam spam'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])
        self.assertEqual(BugReport.objects.count(), 0)

    def test_staff_can_list_and_triage_reports(self):
        BugReport.objects.create(user=self.user, role='student', category='BUG',
                                 message='Something failed badly here')
        staff = User.objects.create_user('bugstaff', password='Xyz@12345',
                                         is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        listing = self.client.get('/admin-panel/bug-reports/')
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, 'Something failed badly here')

        report = BugReport.objects.get()
        self.client.post(f'/admin-panel/bug-reports/{report.pk}/',
                         {'status': 'FIXED', 'admin_note': 'fixed in build 12'})
        report.refresh_from_db()
        self.assertEqual(report.status, 'FIXED')
        self.assertEqual(report.admin_note, 'fixed in build 12')

    def test_students_cannot_open_the_triage_list(self):
        self.assertEqual(self.client.get('/admin-panel/bug-reports/').status_code, 403)

    def test_report_button_is_on_every_page(self):
        body = self.client.get('/dashboard/').content.decode()
        self.assertIn('data-report-open', body)
        self.assertIn('id="report-dialog"', body)


class AddStudentTests(TestCase):
    """The office can add one student without going through a CSV file."""

    def setUp(self):
        self.admin = User.objects.create_user('officeclerk', password='Xyz@12345',
                                              is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)

    def test_form_renders(self):
        response = self.client.get('/admin-panel/students/add/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registration number')

    def test_student_and_login_are_created(self):
        response = self.client.post('/admin-panel/students/add/', {
            'name': 'Anita Kumari',
            'registration_number': 'NEW2024001',
            'branch': 'CS',
            'semester': 1,
            'year_of_admission': 2024,
            'phone': '',
            'email': 'anita@example.edu',
            'father_name': 'Ram Kumar',
            'mother_name': '',
            'date_of_birth': '',
            'address': '',
        })
        self.assertEqual(response.status_code, 302)
        profile = StudentProfile.objects.get(registration_number='NEW2024001')
        self.assertEqual(profile.name, 'Anita Kumari')
        self.assertIsNotNone(profile.user)
        self.assertEqual(profile.user.username, 'NEW2024001')
        self.assertFalse(profile.user.has_usable_password())
        self.assertFalse(profile.is_password_changed)

    def test_duplicate_registration_number_is_rejected(self):
        StudentProfile.objects.create(user=User.objects.create_user('existing', password='X'),
                                      name='Existing', registration_number='DUP001')
        response = self.client.post('/admin-panel/students/add/', {
            'name': 'Copy Cat', 'registration_number': 'DUP001', 'semester': 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'errorlist')
        self.assertEqual(StudentProfile.objects.filter(registration_number='DUP001').count(), 1)

    def test_students_cannot_add_students(self):
        student = User.objects.create_user('notanadmin', password='Xyz@12345')
        StudentProfile.objects.create(user=student, name='S', registration_number='S1',
                                      is_password_changed=True)
        self.client.force_login(student)
        response = self.client.get('/admin-panel/students/add/')
        self.assertIn(response.status_code, (302, 403))
