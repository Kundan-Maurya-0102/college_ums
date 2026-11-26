"""Marks entry grid: one POST for the whole class, validation, CSV, isolation."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from students.models import FacultyProfile, InternalExam, StudentProfile, Subject

User = get_user_model()


def teacher(username, name, subjects):
    user = User.objects.create_user(username, password='TestPass@12345', is_staff=True)
    faculty = FacultyProfile.objects.create(user=user, name=name, department='CS')
    for code, branch, semester, title in subjects:
        faculty.subjects.add(Subject.objects.create(branch=branch, semester=semester,
                                                    subject_code=code, subject_name=title))
    return faculty


def student(username, reg, name, branch='CS', semester=3):
    user = User.objects.create_user(username, password='TestPass@12345')
    return StudentProfile.objects.create(user=user, name=name, registration_number=reg,
                                         branch=branch, semester=semester,
                                         year_of_admission=2023, is_password_changed=True)


class MarksGridTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.faculty = teacher('m-teacher', 'Marks Teacher', [('CS301', 'CS', 3, 'Database')])
        cls.subject = cls.faculty.subjects.first()
        cls.a = student('m-a', 'MG001', 'Aarav')
        cls.b = student('m-b', 'MG002', 'Bhavna')
        cls.outsider = student('m-x', 'MG900', 'Other Branch', 'ME', 5)
        cls.other_faculty = teacher('m-other', 'Other Teacher', [('ME501', 'ME', 5, 'Thermo')])

    def client_for(self, faculty=None):
        c = Client(HTTP_HOST='localhost')
        c.force_login((faculty or self.faculty).user)
        return c

    def url(self, **extra):
        params = {'branch': 'CS', 'semester': 3, 'subject': self.subject.pk}
        params.update(extra)
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        return f'{reverse("teacher_marks")}?{query}'

    def test_grid_has_one_row_per_class_student(self):
        response = self.client_for().get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['rows']), 2)
        self.assertEqual(response.content.decode().count('marks-input'), 2)
        codes = [row['student'].registration_number for row in response.context['rows']]
        self.assertNotIn('MG900', codes)

    def test_inputs_carry_the_maximum(self):
        response = self.client_for().get(self.url(max_marks=25))
        self.assertEqual(response.context['max_marks'], 25)
        self.assertIn('max="25"', response.content.decode())

    def test_saves_every_filled_row_and_skips_blanks(self):
        response = self.client_for().post(reverse('teacher_marks'), {
            'semester': 3, 'branch': 'CS', 'subject': self.subject.pk,
            'exam_type': 'CA1', 'max_marks': 20, 'exam_date': '2026-11-20',
            f'marks_{self.a.pk}': '18', f'marks_{self.b.pk}': '',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        saved = InternalExam.objects.filter(subject=self.subject, exam_type='CA1')
        self.assertEqual(saved.count(), 1)
        self.assertEqual(saved.first().student, self.a)
        self.assertEqual(saved.first().marks_obtained, 18)
        self.assertEqual(saved.first().max_marks, 20)

    def test_second_save_updates_instead_of_duplicating(self):
        client = self.client_for()
        payload = {'semester': 3, 'branch': 'CS', 'subject': self.subject.pk,
                   'exam_type': 'CA1', 'max_marks': 20, 'exam_date': '2026-11-20',
                   f'marks_{self.a.pk}': '10'}
        client.post(reverse('teacher_marks'), payload)
        payload[f'marks_{self.a.pk}'] = '15'
        client.post(reverse('teacher_marks'), payload)
        rows = InternalExam.objects.filter(subject=self.subject, exam_type='CA1')
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().marks_obtained, 15)

    def test_value_above_the_maximum_is_refused(self):
        client = self.client_for()
        response = client.post(reverse('teacher_marks'), {
            'semester': 3, 'branch': 'CS', 'subject': self.subject.pk,
            'exam_type': 'CA1', 'max_marks': 20, 'exam_date': '2026-11-20',
            f'marks_{self.a.pk}': '25',
        }, follow=True)
        self.assertFalse(InternalExam.objects.filter(subject=self.subject).exists())
        self.assertContains(response, 'outside 0–20')

    def test_non_numeric_value_is_refused(self):
        client = self.client_for()
        response = client.post(reverse('teacher_marks'), {
            'semester': 3, 'branch': 'CS', 'subject': self.subject.pk,
            'exam_type': 'CA1', 'max_marks': 20, 'exam_date': '2026-11-20',
            f'marks_{self.a.pk}': 'abc',
        }, follow=True)
        self.assertFalse(InternalExam.objects.filter(subject=self.subject).exists())
        self.assertContains(response, 'not a number')

    def test_cannot_post_another_teachers_subject(self):
        other_subject = self.other_faculty.subjects.first()
        self.client_for().post(reverse('teacher_marks'), {
            'semester': 5, 'branch': 'ME', 'subject': other_subject.pk,
            'exam_type': 'CA1', 'max_marks': 20, 'exam_date': '2026-11-20',
            f'marks_{self.outsider.pk}': '12',
        })
        self.assertFalse(InternalExam.objects.filter(subject=other_subject).exists())

    def test_csv_export_lists_the_grid(self):
        InternalExam.objects.create(student=self.a, subject=self.subject, exam_type='CA1',
                                    marks_obtained=17, max_marks=20,
                                    exam_date='2026-11-20')
        response = self.client_for().get(self.url(exam_type='CA1', export='csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="marks-CS301-CA1.csv"',
                      response['Content-Disposition'])
        body = response.content.decode()
        self.assertEqual(body.splitlines()[0], 'registration_number,name,marks')
        self.assertIn('MG001,Aarav,17', body)
        self.assertIn('MG002,Bhavna,', body)

    def test_csv_export_needs_a_subject_of_mine(self):
        other_subject = self.other_faculty.subjects.first()
        response = self.client_for().get(
            f'{reverse("teacher_marks")}?branch=ME&semester=5&subject={other_subject.pk}&export=csv')
        # no subject of this teacher matches, so the page renders instead of a file
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Content-Type'), 'text/csv')
        self.assertNotIn('attachment;', response.get('Content-Disposition') or '')

    def test_student_and_anonymous_cannot_reach_it(self):
        c = Client(HTTP_HOST='localhost')
        c.force_login(self.a.user)
        self.assertEqual(c.get(reverse('teacher_marks')).status_code, 302)
        self.assertEqual(Client(HTTP_HOST='localhost').get(reverse('teacher_marks')).status_code, 302)

    def test_query_count_is_flat_as_the_class_grows(self):
        client = self.client_for()

        def count():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(client.get(self.url()).status_code, 200)
            return len(ctx.captured_queries)

        before = count()
        for i in range(12):
            student(f'bulk{i}', f'BG{i:03d}', f'Bulk {i}')
        after = count()
        self.assertLessEqual(after, before + 2, f'{before} -> {after} for 12 more students')

    def test_grid_script_is_shipped(self):
        from pathlib import Path

        from django.conf import settings
        path = Path(settings.BASE_DIR) / 'static' / 'js' / 'marks-grid.js'
        self.assertTrue(path.exists())
        body = path.read_text()
        for needle in ('ArrowDown', 'beforeunload', 'data-csv-input', 'is-invalid'):
            self.assertIn(needle, body)
