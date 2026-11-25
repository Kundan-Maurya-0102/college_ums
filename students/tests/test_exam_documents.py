"""Exam documents: hall tickets, marksheets, bulk ZIP, verification and access control."""
import io
import zipfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from students import exams
from students.models import (
    AuditLog,
    ExamDocument,
    ExamSchedule,
    FacultyProfile,
    SemesterResult,
    StudentProfile,
    Subject,
)

User = get_user_model()
PDF_MAGIC = b'%PDF-'


def make_student(username, reg, name, branch='CS', semester=3):
    user = User.objects.create_user(username=username, password='TestPass@12345')
    return StudentProfile.objects.create(
        user=user, name=name, registration_number=reg, branch=branch,
        semester=semester, year_of_admission=2023, is_password_changed=True)


def pdf_text(blob):
    import pypdf
    return ''.join(page.extract_text() or '' for page in pypdf.PdfReader(io.BytesIO(blob)).pages)


class ExamFixture:
    @staticmethod
    def seed():
        office = User.objects.create_user(username='office-exam', password='TestPass@12345',
                                          is_staff=True)
        teacher_user = User.objects.create_user(username='teach-exam', password='TestPass@12345')
        teacher = FacultyProfile.objects.create(user=teacher_user, name='Exam Teacher')

        mine = make_student('exam-mine', 'EXAM001', 'Mine Student')
        other = make_student('exam-other', 'EXAM002', 'Other Student')
        far = make_student('exam-far', 'EXAM900', 'Far Student', branch='ME', semester=5)

        subject = Subject.objects.create(branch='CS', semester=3, subject_code='CS301',
                                        subject_name='Data Structures', credits=4)
        other_subject = Subject.objects.create(branch='CS', semester=3, subject_code='CS302',
                                              subject_name='Digital Electronics', credits=3)
        teacher.subjects.add(subject)

        today = timezone.localdate()
        SemesterResult.objects.create(student=mine, semester=3, subject=subject,
                                      internal_marks=22, external_marks=58, is_pass=True)
        SemesterResult.objects.create(student=mine, semester=3, subject=other_subject,
                                      internal_marks=10, external_marks=25, is_pass=False)
        SemesterResult.objects.create(student=other, semester=3, subject=subject,
                                      internal_marks=30, external_marks=65, is_pass=True)
        SemesterResult.objects.create(student=far, semester=5, subject=subject,
                                      internal_marks=1, external_marks=1, is_pass=False)

        ExamSchedule.objects.create(branch='CS', semester=3, subject=subject,
                                    exam_type='END_SEM', exam_date=today + timedelta(days=5),
                                    start_time=timezone.datetime(2020, 1, 1, 10).time(),
                                    end_time=timezone.datetime(2020, 1, 1, 13).time(),
                                    room='Hall-A')
        return {'office': office, 'teacher': teacher, 'mine': mine, 'other': other,
                'far': far, 'subject': subject,
                'other_subject': other_subject}


class HallTicketTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = ExamFixture.seed()

    def login(self, profile):
        client = Client(HTTP_HOST='localhost')
        client.force_login(profile.user)
        return client

    def test_student_gets_a_real_pdf_with_verification_code(self):
        response = self.login(self.data['mine']).get(reverse('student_hall_ticket'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(PDF_MAGIC))
        self.assertIn('EXAM001', response['Content-Disposition'])

        document = ExamDocument.objects.get(student=self.data['mine'],
                                            kind=ExamDocument.KIND_HALL_TICKET)
        text = pdf_text(response.content)
        self.assertIn(document.verification_code, text)
        self.assertIn('HALL TICKET', text)
        self.assertIn('Hall-A', text)
        self.assertIn('Mine Student', text)
        self.assertIn('Data Structures', text)
        # QR points at the public verification page
        self.assertIn(document.verify_url(), text)

    def test_hall_ticket_only_contains_upcoming_papers(self):
        past = ExamSchedule.objects.create(
            branch='CS', semester=3, subject=self.data['other_subject'], exam_type='MID_SEM',
            exam_date=timezone.localdate() - timedelta(days=40),
            start_time=timezone.datetime(2020, 1, 1, 10).time(),
            end_time=timezone.datetime(2020, 1, 1, 12).time())
        text = pdf_text(self.login(self.data['mine']).get(reverse('student_hall_ticket')).content)
        self.assertNotIn('Digital Electronics', text)
        self.assertTrue(past.exam_date < timezone.localdate())

    def test_one_document_row_per_day_is_reused(self):
        client = self.login(self.data['mine'])
        client.get(reverse('student_hall_ticket'))
        client.get(reverse('student_hall_ticket'))
        self.assertEqual(
            ExamDocument.objects.filter(student=self.data['mine']).count(), 1)
        document = ExamDocument.objects.get(student=self.data['mine'])
        self.assertEqual(document.downloads, 2)      # both downloads counted

    def test_generation_and_download_are_audited(self):
        client = self.login(self.data['mine'])
        client.get(reverse('student_hall_ticket'))
        actions = list(AuditLog.objects.values_list('action', flat=True))
        self.assertIn('exam.hall_ticket', actions)
        entry = AuditLog.objects.filter(action='exam.hall_ticket').first()
        self.assertIn('EXAM001', entry.detail)


class MarksheetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = ExamFixture.seed()

    def login(self, profile):
        client = Client(HTTP_HOST='localhost')
        client.force_login(profile.user)
        return client

    def test_marksheet_shows_marks_grades_and_backlogs(self):
        response = self.login(self.data['mine']).get(reverse('student_marksheet'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(PDF_MAGIC))
        text = pdf_text(response.content)
        for expected in ('CONSOLIDATED MARKSHEET', 'Data Structures', 'Digital Electronics',
                         'Backlogs to clear', 'Fail', 'SGPA', 'CGPA'):
            self.assertIn(expected, text)

    def test_sgpa_and_cgpa_use_credits_and_grade_points(self):
        data = exams.marksheet_data(self.data['mine'])
        # 22+58=80 -> A+ (9 points, 4 credits); 10+25=35 -> F (0 points, 3 credits)
        self.assertEqual(data['sgpa'], round((4 * 9 + 3 * 0) / 7, 2))
        self.assertEqual(data['cgpa'], data['sgpa'])
        self.assertEqual(data['credits_total'], 7)
        self.assertEqual(data['credits_earned'], 4)
        self.assertEqual(len(data['backlogs']), 1)
        self.assertIn('Fail', data['result'])

    def test_passing_student_has_no_backlogs(self):
        data = exams.marksheet_data(self.data['other'])
        self.assertEqual(data['backlogs'], [])
        self.assertEqual(data['result'], 'Pass')
        self.assertEqual(data['credits_earned'], 4)   # only one subject published

    def test_marksheet_without_results_still_renders(self):
        lonely = make_student('exam-lonely', 'EXAM777', 'No Result Student')
        response = Client(HTTP_HOST='localhost')
        response.force_login(lonely.user)
        pdf_response = response.get(reverse('student_marksheet'))
        self.assertEqual(pdf_response.status_code, 200)
        text = pdf_text(pdf_response.content)
        self.assertIn('No results published', text)
        self.assertIn('Not published', text)

    def test_semester_parameter_cannot_reach_another_students_marks(self):
        """?semester= only narrows *my* rows; the student id never comes from the URL."""
        response = self.login(self.data['far']).get(
            reverse('student_marksheet') + '?semester=3')
        text = pdf_text(response.content)
        self.assertNotIn('Mine Student', text)
        self.assertNotIn('EXAM001', text)


class AccessControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = ExamFixture.seed()

    def test_student_cannot_download_another_students_document(self):
        mine = self.data['mine']
        other_document = exams.issue_document(
            ExamDocument.KIND_HALL_TICKET, self.data['other'], 3, user=mine.user)
        client = Client(HTTP_HOST='localhost')
        client.force_login(mine.user)
        response = client.get(
            reverse('exam_document_download', args=[other_document.verification_code]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AuditLog.objects.filter(action='exam.download_denied').exists())

    def test_own_code_downloads_fine(self):
        document = exams.issue_document(
            ExamDocument.KIND_HALL_TICKET, self.data['mine'], 3, user=self.data['mine'].user)
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        response = client.get(reverse('exam_document_download', args=[document.verification_code]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(PDF_MAGIC))

    def test_anonymous_cannot_download_but_can_verify(self):
        document = exams.issue_document(
            ExamDocument.KIND_HALL_TICKET, self.data['mine'], 3)
        anonymous = Client(HTTP_HOST='localhost')
        response = anonymous.get(reverse('exam_document_download', args=[document.verification_code]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

        verify = anonymous.get(reverse('exam_document_verify', args=[document.verification_code]))
        self.assertEqual(verify.status_code, 200)
        body = verify.content.decode()
        self.assertIn('Valid', body)
        self.assertIn(document.verification_code, body)
        # no marks, and the registration number is masked
        self.assertNotIn('Mine Student', body)
        self.assertNotIn('EXAM001', body)
        self.assertIn('EXA**01', body)          # EXAM001 with the middle masked

    def test_unknown_code_says_not_found(self):
        response = Client(HTTP_HOST='localhost').get(
            reverse('exam_document_verify', args=['NOSUCHCODE99']))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Not found', response.content.decode())

    def test_cancelled_document_is_reported_as_cancelled(self):
        document = exams.issue_document(
            ExamDocument.KIND_HALL_TICKET, self.data['mine'], 3)
        document.is_valid = False
        document.save(update_fields=['is_valid'])
        body = Client(HTTP_HOST='localhost').get(
            reverse('exam_document_verify', args=[document.verification_code])).content.decode()
        self.assertIn('Cancelled', body)

    def test_teacher_can_only_see_their_own_class(self):
        teacher = self.data['teacher']
        mine_doc = exams.issue_document(ExamDocument.KIND_HALL_TICKET, self.data['mine'], 3)
        far_doc = exams.issue_document(ExamDocument.KIND_HALL_TICKET, self.data['far'], 5)
        client = Client(HTTP_HOST='localhost')
        client.force_login(teacher.user)
        self.assertEqual(client.get(
            reverse('exam_document_download', args=[mine_doc.verification_code])).status_code, 200)
        self.assertEqual(client.get(
            reverse('exam_document_download', args=[far_doc.verification_code])).status_code, 403)

    def test_student_cannot_reach_the_staff_bulk_page(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        self.assertEqual(client.get(reverse('admin_exam_documents')).status_code, 403)
        response = client.post(reverse('admin_exam_documents_bulk'),
                               {'branch': 'CS', 'semester': 3, 'kind': 'HALL_TICKET'})
        self.assertEqual(response.status_code, 403)


class BulkGenerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = ExamFixture.seed()

    def staff_client(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['office'])
        return client

    def test_bulk_hall_tickets_zip_has_one_pdf_per_student(self):
        response = self.staff_client().post(reverse('admin_exam_documents_bulk'), {
            'branch': 'CS', 'semester': 3, 'kind': 'HALL_TICKET', 'exam_type': 'END_SEM'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        names = archive.namelist()
        self.assertEqual(len(names), 2)          # two CS sem-3 students
        self.assertTrue(all(name.endswith('.pdf') for name in names))
        for name in names:
            self.assertTrue(archive.read(name).startswith(PDF_MAGIC))

        self.assertEqual(ExamDocument.objects.filter(kind='HALL_TICKET').count(), 2)
        self.assertTrue(AuditLog.objects.filter(action='exam.bulk_generate').exists())

    def test_bulk_marksheets_zip(self):
        response = self.staff_client().post(reverse('admin_exam_documents_bulk'), {
            'branch': 'CS', 'semester': 3, 'kind': 'MARKSHEET'})
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        self.assertEqual(len(archive.namelist()), 2)
        text = pdf_text(archive.read(archive.namelist()[0]))
        self.assertIn('CONSOLIDATED MARKSHEET', text)

    def test_empty_class_redirects_with_a_message(self):
        response = self.staff_client().post(reverse('admin_exam_documents_bulk'), {
            'branch': 'EE', 'semester': 6, 'kind': 'HALL_TICKET'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('No students in that class', response.content.decode())

    def test_teacher_cannot_generate_for_a_foreign_class(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['teacher'].user)
        response = client.post(reverse('admin_exam_documents_bulk'), {
            'branch': 'ME', 'semester': 5, 'kind': 'HALL_TICKET'})
        self.assertEqual(response.status_code, 403)

    def test_teacher_can_generate_for_their_own_class(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['teacher'].user)
        response = client.post(reverse('admin_exam_documents_bulk'), {
            'branch': 'CS', 'semester': 3, 'kind': 'HALL_TICKET'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')


class ExamDocumentsPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = ExamFixture.seed()

    def test_student_page_lists_their_documents_only(self):
        exams.issue_document(ExamDocument.KIND_HALL_TICKET, self.data['mine'], 3)
        exams.issue_document(ExamDocument.KIND_HALL_TICKET, self.data['other'], 3)
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['mine'].user)
        response = client.get(reverse('exam_documents'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('Hall ticket', body)
        mine = ExamDocument.objects.get(student=self.data['mine'])
        other = ExamDocument.objects.get(student=self.data['other'])
        self.assertIn(mine.verification_code, body)
        self.assertNotIn(other.verification_code, body)

    def test_staff_page_lists_the_class(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.data['office'])
        response = client.get(reverse('admin_exam_documents') + '?branch=CS&semester=3')
        self.assertEqual(response.status_code, 200)
        self.assertIn('EXAM001', response.content.decode())


class ExamIsolationTests(TestCase):
    """College A's deployment must never render or resolve College B's documents.

    College B keeps its rows in its own database, with the same primary keys.
    """

    databases = {'default', 'college_b'}

    @classmethod
    def setUpTestData(cls):
        cls.mine = make_student('iso-a', 'AAAA0001', 'A College Student')
        subject = Subject.objects.create(branch='CS', semester=3, subject_code='CS301',
                                        subject_name='A College Subject', credits=4)
        SemesterResult.objects.create(student=cls.mine, semester=3, subject=subject,
                                      internal_marks=25, external_marks=60, is_pass=True)

        b_user = User.objects.db_manager('college_b').create_user(
            username='iso-b', password='TestPass@12345')
        cls.b_student = StudentProfile.objects.using('college_b').create(
            pk=cls.mine.pk, user=b_user, name='B COLLEGE STUDENT',
            registration_number='BBBB0001', branch='CS', semester=3,
            year_of_admission=2023, is_password_changed=True)
        b_subject = Subject.objects.using('college_b').create(
            pk=subject.pk, branch='CS', semester=3, subject_code='CS301',
            subject_name='B COLLEGE SUBJECT', credits=4)
        SemesterResult.objects.using('college_b').create(
            student=cls.b_student, semester=3, subject=b_subject, internal_marks=1,
            external_marks=1, is_pass=False)
        cls.b_document = ExamDocument.objects.using('college_b').create(
            kind=ExamDocument.KIND_HALL_TICKET, student=cls.b_student, semester=3,
            verification_code='BCOLLEGECODE')

    def test_marksheet_of_a_never_mentions_the_other_college(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.mine.user)
        text = pdf_text(client.get(reverse('student_marksheet')).content)
        self.assertIn('A College Student', text)
        self.assertIn('A College Subject', text)
        self.assertNotIn('B COLLEGE STUDENT', text)
        self.assertNotIn('B COLLEGE SUBJECT', text)
        self.assertNotIn('BBBB0001', text)

    def test_other_colleges_verification_code_does_not_resolve_here(self):
        body = Client(HTTP_HOST='localhost').get(
            reverse('exam_document_verify', args=['BCOLLEGECODE'])).content.decode()
        self.assertIn('Not found', body)
        self.assertNotIn('B COLLEGE STUDENT', body)

    def test_documents_created_here_never_land_in_the_other_database(self):
        client = Client(HTTP_HOST='localhost')
        client.force_login(self.mine.user)
        client.get(reverse('student_hall_ticket'))
        self.assertEqual(ExamDocument.objects.filter(student=self.mine).count(), 1)
        self.assertEqual(
            ExamDocument.objects.using('college_b').filter(student_id=self.mine.pk).count(), 1)
        self.assertNotEqual(
            ExamDocument.objects.get(student=self.mine).verification_code, 'BCOLLEGECODE')


class ExamGradePointTests(TestCase):
    def test_grade_points_match_the_printed_legend(self):
        expected = {'O': 10, 'A+': 9, 'A': 8, 'B+': 7, 'B': 6, 'C': 5, 'F': 0}
        for grade, point in expected.items():
            self.assertEqual(exams.grade_point(grade), point)
        self.assertEqual(exams.grade_point('a+'), 9)      # case-insensitive
        self.assertEqual(exams.grade_point(''), 0)

    def test_gpa_of_no_rows_is_none_not_zero(self):
        self.assertIsNone(exams.gpa([]))
