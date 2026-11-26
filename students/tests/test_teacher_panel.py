"""Teacher panel: own classes only, the new dashboard data, and a flat query count."""
from datetime import time as dt_time
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from students.models import (
    Attendance,
    ClassSchedule,
    FacultyProfile,
    LeaveApplication,
    Notice,
    StudentProfile,
    Subject,
)

User = get_user_model()


def make_teacher(username, name, subject_codes=()):
    # teachers are staff accounts with a FacultyProfile (see views.common.is_teacher)
    user = User.objects.create_user(username=username, password='TestPass@12345', is_staff=True)
    faculty = FacultyProfile.objects.create(user=user, name=name, department='CS')
    for code, branch, semester, title in subject_codes:
        subject = Subject.objects.create(branch=branch, semester=semester,
                                         subject_code=code, subject_name=title)
        faculty.subjects.add(subject)
    return faculty


def make_student(username, reg, name, branch='CS', semester=3):
    user = User.objects.create_user(username=username, password='TestPass@12345')
    return StudentProfile.objects.create(user=user, name=name, registration_number=reg,
                                         branch=branch, semester=semester,
                                         year_of_admission=2023, is_password_changed=True)


class TeacherDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mine = make_teacher('t-mine', 'My Teacher',
                                [('CS301', 'CS', 3, 'Database Systems')])
        cls.other = make_teacher('t-other', 'Other Teacher',
                                 [('ME501', 'ME', 5, 'Machine Design')])

        cls.subject = cls.mine.subjects.first()
        cls.other_subject = cls.other.subjects.first()

        cls.student = make_student('s-mine', 'T001', 'My Student')
        cls.other_student = make_student('s-other', 'T999', 'Other Class Student', 'ME', 5)

        today = timezone.localdate()
        ClassSchedule.objects.create(subject=cls.subject, faculty=cls.mine,
                                     weekday=today.weekday(), start_time=dt_time(9),
                                     end_time=dt_time(10), room='R-9')
        for i in range(3):
            Attendance.objects.create(student=cls.student, subject=cls.subject,
                                      date=today - timedelta(days=i), is_present=i != 0)
        Attendance.objects.create(student=cls.other_student, subject=cls.other_subject,
                                  date=today, is_present=True)
        Notice.objects.create(title='General notice', content='x', created_by=cls.mine)
        LeaveApplication.objects.create(student=cls.student, leave_type='SICK',
                                        from_date=today, to_date=today, reason='fever')

    def client_for(self, faculty):
        client = Client(HTTP_HOST='localhost')
        client.force_login(faculty.user)
        return client

    def test_dashboard_renders_for_the_teacher(self):
        response = self.client_for(self.mine).get(reverse('teacher_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'teacher/shell.html')
        self.assertEqual(response.context['subject_count'], 1)
        self.assertEqual(response.context['student_count'], 1)
        self.assertEqual(len(response.context['classes_today']), 1)

    def test_only_my_classes_are_counted(self):
        data = self.client_for(self.mine).get(reverse('teacher_dashboard')).context
        rows = data['subject_rows']
        self.assertEqual([row['subject'].subject_code for row in rows], ['CS301'])
        self.assertNotIn('ME501', [row['subject'].subject_code for row in rows])
        self.assertEqual(data['at_risk'][0]['student'].registration_number, 'T001')
        self.assertNotIn('T999', [item['student'].registration_number for item in data['at_risk']])

    def test_another_teachers_dashboard_is_different(self):
        body = self.client_for(self.other).get(reverse('teacher_dashboard')).content.decode()
        self.assertIn('ME501', body)
        self.assertNotIn('CS301', body)

    def test_students_cannot_open_the_teacher_panel(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.student.user)
        for name in ('teacher_dashboard', 'teacher_take_attendance', 'teacher_marks',
                     'teacher_students', 'teacher_notices'):
            with self.subTest(view=name):
                response = client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn('/login/', response['Location'])

    def test_anonymous_is_redirected(self):
        response = Client(HTTP_HOST='localhost').get(reverse('teacher_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_queries_do_not_grow_with_students(self):
        client = self.client_for(self.mine)

        def count():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(client.get(reverse('teacher_dashboard')).status_code, 200)
            return len(ctx.captured_queries)

        before = count()
        for i in range(12):
            student = make_student(f'bulk{i}', f'BULK{i:03d}', f'Bulk {i}')
            Attendance.objects.create(student=student, subject=self.subject,
                                      date=timezone.localdate(), is_present=i % 2 == 0)
        after = count()
        self.assertLessEqual(after, before + 3, f'{before} -> {after} queries for 12 more students')

    def test_pending_work_counts_are_scoped(self):
        pending = self.client_for(self.mine).get(reverse('teacher_dashboard')).context['pending']
        by_key = {item['key']: item['count'] for item in pending}
        self.assertEqual(by_key['attendance'], 0, 'attendance was taken today for the only class')
        self.assertEqual(by_key['leave'], 1)


class TeacherAttendanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.faculty = make_teacher('t-att', 'Att Teacher', [('CS401', 'CS', 4, 'Algorithms')])
        cls.subject = cls.faculty.subjects.first()
        cls.students = [make_student(f'att{i}', f'ATT{i:03d}', f'Att Student {i}', 'CS', 4)
                        for i in range(3)]

    def teacher_client(self):
        c = Client(HTTP_HOST='localhost')
        c.force_login(self.faculty.user)
        return c

    def test_page_lists_only_the_selected_class(self):
        response = self.teacher_client().get(reverse('teacher_take_attendance'),
                                     {'subject': self.subject.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['students']), 3)

    def test_all_present_by_default_and_saving_marks_absentees(self):
        client = self.teacher_client()
        page = client.get(reverse('teacher_take_attendance'), {'subject': self.subject.pk})
        self.assertFalse(page.context['has_attendance'])

        absent = self.students[1]
        response = client.post(reverse('teacher_take_attendance'), {
            'subject': self.subject.pk,
            'date': timezone.localdate().isoformat(),
            'present_student_ids': [self.students[0].pk, self.students[2].pk],
        })
        self.assertIn(response.status_code, (200, 302))

        marked = Attendance.objects.filter(subject=self.subject, date=timezone.localdate())
        self.assertEqual(marked.count(), 3)
        self.assertFalse(marked.get(student=absent).is_present)

    def test_cannot_mark_another_teachers_subject(self):
        other = make_teacher('t-other2', 'Other', [('ME402', 'ME', 4, 'Thermo')])
        self.teacher_client().post(reverse('teacher_take_attendance'), {
            'subject': other.subjects.first().pk,
            'date': timezone.localdate().isoformat(),
            'present_student_ids': [],
        })
        self.assertFalse(Attendance.objects.filter(subject=other.subjects.first()).exists())


class TeacherStudentsListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.faculty = make_teacher('t-list', 'List Teacher', [('CS201', 'CS', 2, 'Data Structures')])
        cls.subject = cls.faculty.subjects.first()
        cls.a = make_student('ls-a', 'LS001', 'Aarav Sharma', 'CS', 2)
        cls.b = make_student('ls-b', 'LS002', 'Bhavna Rao', 'CS', 2)
        cls.hidden = make_student('ls-c', 'LS900', 'Other Branch Student', 'ME', 2)

    def teacher_client(self):
        c = Client(HTTP_HOST='localhost')
        c.force_login(self.faculty.user)
        return c

    def test_search_filters_and_stays_inside_the_class(self):
        response = self.teacher_client().get(reverse('teacher_students'),
                                     {'subject': self.subject.pk, 'q': 'aarav'})
        rows = response.context['rows']
        self.assertEqual([row['student'].registration_number for row in rows], ['LS001'])

        all_rows = self.teacher_client().get(reverse('teacher_students'),
                                     {'subject': self.subject.pk}).context['rows']
        self.assertNotIn('LS900', [row['student'].registration_number for row in all_rows])

    def test_attendance_percentage_is_one_query_not_per_student(self):
        Attendance.objects.create(student=self.a, subject=self.subject,
                                  date=timezone.localdate(), is_present=True)
        client = self.teacher_client()
        url = reverse('teacher_students') + f'?subject={self.subject.pk}'

        with CaptureQueriesContext(connection) as ctx:
            response = client.get(url)
        self.assertEqual(response.status_code, 200)
        queries = len(ctx.captured_queries)
        self.assertLess(queries, 25, f'{queries} queries for a small class (N+1 regression?)')
        percents = {row['student'].registration_number: row['percent']
                    for row in response.context['rows']}
        self.assertEqual(percents['LS001'], 100.0)
        # no attendance marked yet -> shown as '—', not a misleading 0%
        self.assertIsNone(percents['LS002'])


class TeacherSharedUIFilesTests(TestCase):
    def test_teacher_pages_ship_the_attendance_script(self):
        from pathlib import Path

        from django.conf import settings
        path = Path(settings.BASE_DIR) / 'static' / 'js' / 'teacher-attendance.js'
        self.assertTrue(path.exists())
        self.assertIn('all-present', path.read_text())
