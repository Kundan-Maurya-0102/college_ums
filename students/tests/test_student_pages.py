"""The student pages the dashboard links to: own data only, never a dead link."""
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from students.models import Attendance, Notice, StudyMaterial, Subject
from students.tests.test_dashboard_redesign import DashboardFixture

PAGES = ('student_attendance', 'student_results', 'student_timetable',
         'student_notices', 'student_materials')


class StudentPageAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DashboardFixture.seed()

    def login(self, profile):
        client = Client(HTTP_HOST='localhost')
        client.force_login(profile.user)
        return client

    def test_every_page_renders_for_the_student(self):
        client = self.login(self.data['mine'])
        for name in PAGES:
            with self.subTest(page=name):
                response = client.get(reverse(name))
                self.assertEqual(response.status_code, 200, response.content[:400])
                self.assertEqual(response.context['profile'].pk, self.data['mine'].pk)
                self.assertTemplateUsed(response, f'student/{name.removeprefix("student_")}.html')

    def test_anonymous_visitors_are_sent_to_login(self):
        client = Client(HTTP_HOST='localhost')
        for name in PAGES:
            with self.subTest(page=name):
                response = client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn('/login/', response['Location'])

    def test_only_the_own_rows_are_listed(self):
        client = self.login(self.data['mine'])

        attendance = client.get(reverse('student_attendance'))
        rows = attendance.context['rows']
        self.assertEqual([row['subject'].subject_code for row in rows], ['CS301'])
        self.assertEqual(attendance.context['held'], 4)
        self.assertEqual(attendance.context['attended'], 3)

        results = client.get(reverse('student_results'))
        self.assertEqual([block['semester'] for block in results.context['semesters']], [3])
        # the model derives the grade from the marks (80 marks -> A+ -> 9.0)
        self.assertEqual(results.context['cgpa'], 9.0)

        materials = client.get(reverse('student_materials'))
        grouped = materials.context['grouped']
        self.assertEqual([subject.subject_code for subject in grouped], ['CS301'])
        self.assertEqual([item.title for item in grouped[self.data['subject']]['materials']],
                         ['My notes'])

    def test_another_students_marks_never_appear(self):
        """Student B may not see A's result rows even though both have results."""
        other_subject = Subject.objects.create(branch='ME', semester=5,
                                              subject_code='ME599', subject_name='Only B')
        from students.models import SemesterResult
        SemesterResult.objects.create(student=self.data['other'], semester=5,
                                      subject=other_subject, internal_marks=1,
                                      external_marks=1, total_marks=2, grade='F',
                                      is_pass=False)

        client = self.login(self.data['mine'])
        body = client.get(reverse('student_results')).content.decode()
        self.assertNotIn('ME599', body)
        self.assertNotIn('Only B', body)

    def test_notices_page_hides_other_classes(self):
        client = self.login(self.data['mine'])
        response = client.get(reverse('student_notices'))
        titles = [entry['notice'].title for entry in response.context['entries']]
        self.assertIn('General notice', titles)
        self.assertIn('Class message', titles)
        self.assertNotIn('Secret other class', titles)

    def test_empty_student_sees_empty_states_not_errors(self):
        from students.tests.test_dashboard_redesign import make_student

        fresh = make_student('stu-empty', 'EMPTY001', 'Fresh Student', branch='EC', semester=1)
        client = self.login(fresh)
        for name in PAGES:
            with self.subTest(page=name):
                response = client.get(reverse(name))
                self.assertEqual(response.status_code, 200, response.content[:400])

        # Pages that would list rows show their empty state instead of an error.
        self.assertEqual(client.get(reverse('student_attendance')).context['rows'], [])
        self.assertFalse(client.get(reverse('student_results')).context['has_results'])
        self.assertFalse(client.get(reverse('student_timetable')).context['has_slots'])
        self.assertFalse(client.get(reverse('student_materials')).context['has_any'])
        self.assertContains(client.get(reverse('student_attendance')), 'No subjects assigned')
        self.assertContains(client.get(reverse('student_results')), 'No result published')
        self.assertContains(client.get(reverse('student_timetable')), 'No timetable published')
        self.assertContains(client.get(reverse('student_materials')), 'No material or assignment')

    def test_pages_do_not_offer_a_student_id_in_the_url(self):
        """A student cannot ask for somebody else's rows by changing a parameter."""
        client = self.login(self.data['mine'])
        response = client.get(reverse('student_attendance'),
                              {'student': self.data['other'].pk})
        self.assertEqual(response.context['profile'].pk, self.data['mine'].pk)

    def test_attendance_state_thresholds(self):
        client = self.login(self.data['mine'])

        def state():
            return client.get(reverse('student_attendance')).context['rows'][0]['state']

        self.assertEqual(state(), 'ok')  # 3 of 4 = exactly 75%

        # one more absence: 3 of 5 = 60% -> yellow, not red
        Attendance.objects.create(student=self.data['mine'], subject=self.data['subject'],
                                  date=timezone.localdate(), is_present=False)
        self.assertEqual(state(), 'watch')

        # another absence: 3 of 6 = 50% -> red
        Attendance.objects.create(student=self.data['mine'], subject=self.data['subject'],
                                  date=timezone.localdate() - timedelta(days=9),
                                  is_present=False)
        self.assertEqual(state(), 'low')

        # never marked: no percentage at all, and not counted as red
        empty_subject = Subject.objects.create(branch='CS', semester=3,
                                              subject_code='CS399', subject_name='No classes')
        rows = client.get(reverse('student_attendance')).context['rows']
        extra = [row for row in rows if row['subject'].pk == empty_subject.pk][0]
        self.assertEqual(extra['state'], 'none')
        self.assertIsNone(extra['percent'])


class DashboardSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DashboardFixture.seed()

    def login(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        return client

    def test_search_filters_subjects(self):
        client = self.login()
        response = client.get(reverse('student_dashboard'), {'q': 'database'})
        self.assertEqual(response.context['query'], 'database')
        self.assertTrue(response.context['is_searching'])
        self.assertEqual([row['subject'].subject_code for row in response.context['course_rows']],
                         ['CS301'])

        empty = client.get(reverse('student_dashboard'), {'q': 'nothing-matches-this'})
        self.assertEqual(empty.context['course_rows'], [])

    def test_search_never_reaches_another_class(self):
        client = self.login()
        response = client.get(reverse('student_dashboard'), {'q': 'Only B'})
        codes = [row['subject'].subject_code for row in response.context['course_rows']]
        self.assertNotIn('ME599', codes)
        self.assertNotIn('ME501', codes)

    def test_search_box_is_rendered_and_clears(self):
        client = self.login()
        body = client.get(reverse('student_dashboard')).content.decode()
        self.assertIn('name="q"', body)
        self.assertIn('action="/dashboard/"', body)
        searching = client.get(reverse('student_dashboard'), {'q': 'database'}).content.decode()
        self.assertIn('value="database"', searching)

    def test_giant_query_string_is_truncated(self):
        client = self.login()
        response = client.get(reverse('student_dashboard'), {'q': 'x' * 500})
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.context['query']), 60)


class NoDeadLinkTests(TestCase):
    """Every href on the dashboard must resolve — no `href="#"` placeholders."""

    @classmethod
    def setUpTestData(cls):
        cls.data = DashboardFixture.seed()

    def test_no_placeholder_hrefs(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        for url in ['/dashboard/', '/attendance/', '/results/', '/timetable/',
                    '/notices/', '/materials/']:
            with self.subTest(url=url):
                body = client.get(url).content.decode()
                self.assertNotIn('href="#"', body)

    def test_card_footers_point_at_real_pages(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        body = client.get('/dashboard/').content.decode()
        for name in ('student_notices', 'student_fees', 'student_materials',
                     'student_events', 'student_exam_schedule', 'student_hall_ticket',
                     'student_results', 'student_marksheet', 'student_attendance',
                     'student_timetable'):
            with self.subTest(link=name):
                self.assertIn(reverse(name), body, f'{name} is missing from the dashboard')

    def test_contacts_panel_uses_the_college_branding(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        response = client.get('/dashboard/')
        body = response.content.decode()
        self.assertIn('dash-contact-panel', body)
        if response.context['COLLEGE_PHONE']:
            self.assertIn(response.context['COLLEGE_PHONE'], body)


class UnreadNoticeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DashboardFixture.seed()

    def test_new_notice_is_marked_unread_until_seen(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        # the dashboard stamps "seen now", so anything older counts as read
        client.get(reverse('student_dashboard'))
        first = client.get(reverse('student_notices'))
        self.assertEqual(first.context['unread'], 0, 'notices older than the last visit are read')

        Notice.objects.create(title='Brand new', content='read me',
                              created_by=self.data['faculty'])
        second = client.get(reverse('student_notices'))
        self.assertEqual(second.context['unread'], 1)

        dashboard = client.get(reverse('student_dashboard'))
        self.assertGreaterEqual(dashboard.context['unread_count'], 1)

    def test_notice_for_another_semester_is_not_counted(self):
        Notice.objects.create(title='Only for 5th sem', content='x',
                              created_by=self.data['faculty'],
                              target_semesters='5')
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        titles = [entry['notice'].title
                  for entry in client.get(reverse('student_notices')).context['entries']]
        self.assertNotIn('Only for 5th sem', titles)


class StudyMaterialIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = DashboardFixture.seed()

    def test_material_of_another_semester_is_hidden(self):
        other_subject = Subject.objects.create(branch='CS', semester=5,
                                              subject_code='CS501', subject_name='Sem 5 only')
        StudyMaterial.objects.create(title='Sem five notes', subject=other_subject,
                                      uploaded_by=self.data['faculty'])
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        body = client.get(reverse('student_materials')).content.decode()
        self.assertNotIn('Sem five notes', body)
        self.assertIn('My notes', body)


class StudentPageQueryBudgetTests(TestCase):
    """More subjects must not mean more queries on any of the new pages."""

    @classmethod
    def setUpTestData(cls):
        cls.data = DashboardFixture.seed()

    def login(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        return client

    def count(self, client, url):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            response = client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)

    def test_query_count_is_flat_as_subjects_grow(self):
        from students.models import ClassSchedule, StudyMaterial, Subject

        client = self.login()
        urls = [reverse('student_attendance'), reverse('student_results'),
                reverse('student_timetable'), reverse('student_materials'),
                reverse('student_dashboard')]
        before = {url: self.count(client, url) for url in urls}

        for i in range(12):
            extra = Subject.objects.create(branch='CS', semester=3,
                                           subject_code=f'CS3{90 + i}', subject_name=f'Extra {i}')
            StudyMaterial.objects.create(title=f'Notes {i}', subject=extra)
            ClassSchedule.objects.create(subject=extra, faculty=self.data['faculty'],
                                         weekday=i % 6, start_time='09:00', end_time='10:00')

        after = {url: self.count(client, url) for url in urls}
        for url in urls:
            with self.subTest(url=url):
                self.assertLessEqual(after[url], before[url] + 2,
                                     f'{url}: {before[url]} -> {after[url]} queries for 12 more subjects')
