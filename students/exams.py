"""Exam documents: the data behind a hall ticket / marksheet, and who may see it.

Kept apart from the PDF layer so the numbers can be tested without parsing a PDF.
Rules that matter:
  * a student can only ever render their own documents (the view passes their own
    profile, never an id from the URL);
  * a marksheet for a semester with no published result still renders, with a clear
    "no results published" line instead of an error;
  * SGPA/CGPA come from credits and grade points, not from raw percentages.
"""
import logging
from datetime import date

from django.conf import settings
from django.utils import timezone

from .models import ExamDocument, ExamSchedule, SemesterResult, StudentProfile, Subject

logger = logging.getLogger(__name__)

GRADE_POINTS = {
    'O': 10, 'A+': 9, 'A': 8, 'B+': 7, 'B': 6, 'C': 5, 'P': 4, 'F': 0,
}

DEFAULT_INSTRUCTIONS = [
    "Carry this hall ticket and a valid photo ID (college ID / Aadhaar) to every exam.",
    "Reach the exam hall 15 minutes before the reporting time; late entry may be refused.",
    "Mobile phones, smart watches and any printed material are not allowed inside the hall.",
    "Use of unfair means leads to cancellation of the paper as per college rules.",
    "Write your registration number on the answer sheet, not your name.",
    "Check the subject, date and room carefully; report mistakes to the exam cell at once.",
]


def grade_point(grade):
    return GRADE_POINTS.get((grade or '').strip().upper(), 0)


def academic_year_for(when):
    """Indian academic year for a date: July–June."""
    when = when or date.today()
    return f'{when.year}-{when.year + 1}' if when.month >= 7 else f'{when.year - 1}-{when.year}'


def instructions():
    configured = (getattr(settings, 'EXAM_INSTRUCTIONS', '') or '').strip()
    if not configured:
        return DEFAULT_INSTRUCTIONS
    return [line.strip() for line in configured.splitlines() if line.strip()] or DEFAULT_INSTRUCTIONS


def verify_base_url(request=None):
    if request is not None:
        return request.build_absolute_uri('/').rstrip('/')
    domain = (getattr(settings, 'COLLEGE_DOMAIN', '') or '').strip()
    scheme = 'https' if not settings.DEBUG else 'http'
    return f'{scheme}://{domain}' if domain else f'{scheme}://localhost:8000'


def issue_document(kind, student, semester=None, exam_type='', user=None):
    """Create (or reuse today's) audit + verification row for one document."""
    if kind == ExamDocument.KIND_MARKSHEET:
        exam_type = ''
    existing = ExamDocument.objects.filter(
        kind=kind, student=student, semester=semester, exam_type=exam_type,
        issued_at__date=timezone.localdate(), is_valid=True).first()
    if existing:
        return existing
    document = ExamDocument.objects.create(
        kind=kind, student=student, semester=semester, exam_type=exam_type,
        verification_code=ExamDocument.new_code(), issued_by=user)
    logger.info('issued %s for %s (code %s) by %s', kind,
                student.registration_number, document.verification_code,
                getattr(user, 'username', 'system'))
    return document


def record_download(document):
    """Count a download without a race on the counter."""
    from django.db.models import F

    ExamDocument.objects.filter(pk=document.pk).update(
        downloads=F('downloads') + 1, last_downloaded_at=timezone.now())


# ── hall ticket ──────────────────────────────────────────────────────────
def hall_ticket_data(student, semester=None, exam_type='', document=None, request=None):
    semester = semester or student.semester
    exams = []
    if student.branch and semester:
        queryset = ExamSchedule.objects.filter(
            branch=student.branch, semester=semester, is_active=True
        ).select_related('subject').order_by('exam_date', 'start_time')
        if exam_type:
            queryset = queryset.filter(exam_type=exam_type)
        # Only upcoming papers, plus anything from the last 3 days (an exam already
        # written today must not vanish from a ticket printed on the same day).
        queryset = queryset.filter(exam_date__gte=timezone.localdate() - timezone.timedelta(days=3))
        exams = list(queryset)

    reference = exams[0].exam_date if exams else timezone.localdate()
    document = document or issue_document(
        ExamDocument.KIND_HALL_TICKET, student, semester, exam_type)
    label = dict(ExamSchedule.EXAM_TYPE_CHOICES).get(exam_type, '') if exam_type else 'All examinations'
    return {
        'student': student,
        'semester': semester,
        'exams': exams,
        'exam_type': exam_type,
        'exam_label': label,
        'academic_year': academic_year_for(reference),
        'instructions': instructions(),
        'verification_code': document.verification_code,
        'verify_url': f"{verify_base_url(request)}{document.verify_url()}",
        'issued_on': timezone.localdate(),
    }


# ── marksheet ────────────────────────────────────────────────────────────
def _rows_for(student, semester=None):
    queryset = (SemesterResult.objects.filter(student=student)
                .select_related('subject').order_by('semester', 'subject__subject_code'))
    if semester is not None:
        queryset = queryset.filter(semester=semester)
    rows = []
    for result in queryset:
        subject = result.subject
        rows.append({
            'code': subject.subject_code,
            'name': subject.subject_name,
            'credits': subject.credits or 0,
            'internal': result.internal_marks,
            'external': result.external_marks,
            'total': result.total_marks,
            'grade': result.grade,
            'is_pass': result.is_pass,
            'point': grade_point(result.grade),
            'semester': result.semester,
        })
    return rows


def gpa(rows):
    """Credit-weighted GPA of the given rows (None when nothing is graded yet)."""
    credits = sum(row['credits'] for row in rows)
    if not credits:
        return None
    score = sum(row['credits'] * row['point'] for row in rows)
    return round(score / credits, 2)


def latest_semester(student):
    return (SemesterResult.objects.filter(student=student)
            .order_by('-semester').values_list('semester', flat=True).first())


def marksheet_data(student, semester=None, document=None, request=None):
    semester = semester or latest_semester(student) or student.semester
    rows = _rows_for(student, semester) if semester is not None else []
    all_rows = _rows_for(student)

    credits_total = sum(row['credits'] for row in rows)
    credits_earned = sum(row['credits'] for row in rows if row['is_pass'])
    backlogs = [row for row in rows if not row['is_pass']]
    sgpa = gpa(rows)
    cgpa = gpa(all_rows)

    if not rows:
        result = 'Not published'
    elif backlogs:
        result = f'Fail — {len(backlogs)} backlog(s)'
    else:
        result = 'Pass'

    document = document or issue_document(
        ExamDocument.KIND_MARKSHEET, student, semester)
    reference = timezone.localdate()
    return {
        'student': student,
        'semester': semester,
        'subjects': rows,
        'backlogs': backlogs,
        'credits_total': credits_total,
        'credits_earned': credits_earned,
        'sgpa': sgpa,
        'cgpa': cgpa,
        'result': result,
        'academic_year': academic_year_for(reference),
        'verification_code': document.verification_code,
        'verify_url': f"{verify_base_url(request)}{document.verify_url()}",
        'issued_on': reference,
        'document': document,
    }


# ── who may do what ──────────────────────────────────────────────────────
def is_exam_staff(user):
    """Admin office (staff) and teachers can generate documents for their classes."""
    return bool(user.is_authenticated and (user.is_staff or hasattr(user, 'facultyprofile')))


def teacher_classes(user):
    """(branch, semester) pairs a teacher is responsible for."""
    faculty = getattr(user, 'facultyprofile', None)
    if not faculty:
        return set()
    return {(subject.branch, subject.semester) for subject in faculty.subjects.all()
            if subject.branch and subject.semester}


def can_issue_for(user, student):
    if not is_exam_staff(user):
        return False
    if user.is_staff:
        return True
    return (student.branch, student.semester) in teacher_classes(user)


def can_view_document(user, document):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    if getattr(user, 'studentprofile', None) is not None:
        return document.student_id == user.studentprofile.pk
    return can_issue_for(user, document.student)


def students_for_class(branch, semester):
    """Class list for bulk generation (ordered, only real profiles)."""
    return (StudentProfile.objects.filter(branch=branch, semester=semester)
            .select_related('user').order_by('registration_number'))


def semesters_with_results():
    return (SemesterResult.objects.values_list('semester', flat=True)
            .distinct().order_by('semester'))


def subjects_for_semester(branch, semester):
    return Subject.objects.filter(branch=branch, semester=semester, is_active=True)
