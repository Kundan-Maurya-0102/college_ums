"""Admin marks_entry server-side validation (mirrors teacher_marks checks)."""
import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from students.forms import InternalExamForm
from students.models import InternalExam, StudentProfile, Subject


class AdminMarksEntryValidationTests(TestCase):
    """Server-side 0..max_marks validation, negative and non-numeric rejection."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='marks_admin', password='Admin@12345', is_staff=True,
        )
        self.client.force_login(self.admin)
        self.student = StudentProfile.objects.create(
            user=User.objects.create_user(username='marks_student'),
            name='Ravi', phone='9876543210',
            registration_number='MK001', branch='CS', semester=1,
        )
        self.subject = Subject.objects.create(
            subject_code='CS101', subject_name='Maths',
            branch='CS', semester=1,
        )
        self.url = reverse('marks_entry')

    def _post(self, marks_obtained, max_marks=100):
        return self.client.post(self.url, {
            'student': self.student.pk,
            'subject': self.subject.pk,
            'exam_type': 'CA1',
            'marks_obtained': marks_obtained,
            'max_marks': max_marks,
            'exam_date': datetime.date.today().isoformat(),
        })

    def test_valid_marks_saved(self):
        resp = self._post(75, 100)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(InternalExam.objects.filter(
            student=self.student, marks_obtained=75,
        ).exists())

    def test_zero_marks_accepted(self):
        resp = self._post(0, 100)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(InternalExam.objects.filter(
            student=self.student, marks_obtained=0,
        ).exists())

    def test_max_marks_exactly_accepted(self):
        resp = self._post(100, 100)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(InternalExam.objects.filter(
            student=self.student, marks_obtained=100,
        ).exists())

    def test_negative_marks_rejected(self):
        resp = self._post(-5, 100)
        self.assertEqual(resp.status_code, 200)  # re-renders form
        self.assertFalse(InternalExam.objects.filter(student=self.student).exists())

    def test_exceeding_max_marks_rejected(self):
        resp = self._post(150, 100)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(InternalExam.objects.filter(student=self.student).exists())

    def test_zero_max_marks_rejected(self):
        resp = self._post(0, 0)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(InternalExam.objects.filter(student=self.student).exists())

    def test_non_numeric_marks_rejected_by_form(self):
        resp = self.client.post(self.url, {
            'student': self.student.pk,
            'subject': self.subject.pk,
            'exam_type': 'CA1',
            'marks_obtained': 'abc',
            'max_marks': 100,
            'exam_date': datetime.date.today().isoformat(),
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(InternalExam.objects.filter(student=self.student).exists())


class InternalExamFormCleanTests(TestCase):
    """Direct form-level validation tests."""

    def setUp(self):
        self.student = StudentProfile.objects.create(
            user=User.objects.create_user(username='form_student'),
            name='Form Student', phone='9876543210',
            registration_number='FM001', branch='CS', semester=1,
        )
        self.subject = Subject.objects.create(
            subject_code='CS201', subject_name='Physics',
            branch='CS', semester=1,
        )

    def _form(self, marks, max_marks):
        return InternalExamForm(data={
            'student': self.student.pk,
            'subject': self.subject.pk,
            'exam_type': 'CA1',
            'marks_obtained': marks,
            'max_marks': max_marks,
            'exam_date': datetime.date.today().isoformat(),
        })

    def test_form_rejects_negative(self):
        f = self._form(-1, 100)
        self.assertFalse(f.is_valid())

    def test_form_rejects_exceeding(self):
        f = self._form(101, 100)
        self.assertFalse(f.is_valid())

    def test_form_accepts_valid(self):
        f = self._form(50, 100)
        self.assertTrue(f.is_valid(), f.errors)
