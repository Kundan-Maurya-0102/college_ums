"""Exam documents: hall tickets and marksheets as PDF, plus bulk generation.

Access rules enforced here (not in the template):
  * a student can only render their **own** profile — the URL never carries a student id;
  * staff can generate for anyone in the deployment, a teacher only for their own classes;
  * downloading by verification code re-checks the same rule;
  * every generation and download writes an audit row, and `/verify/<code>/` is public
    but shows no marks.
"""
import io
import logging
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .. import exams, pdf
from ..audit import log_action
from ..models import ExamDocument, ExamSchedule, StudentProfile

logger = logging.getLogger(__name__)

PDF_HEADERS = {'Content-Disposition': 'inline; filename="{name}"'}
BULK_LIMIT = 500          # one ZIP must not exhaust worker memory


def _student_profile(request):
    return getattr(request.user, 'studentprofile', None)


def _pdf_response(content, filename, inline=True):
    response = HttpResponse(content, content_type='application/pdf')
    disposition = 'inline' if inline else 'attachment'
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    response['Cache-Control'] = 'private, no-store'
    return response


# ── student side ─────────────────────────────────────────────────────────
@login_required(login_url='/login/')
@require_GET
def student_hall_ticket(request):
    """The student's own hall ticket (optional ?exam_type=END_SEM)."""
    profile = _student_profile(request)
    if profile is None:
        messages.error(request, "No student profile is linked to this account.")
        return redirect('student_login')

    exam_type = request.GET.get('exam_type', '').strip()
    valid_types = {value for value, _label in ExamSchedule.EXAM_TYPE_CHOICES}
    if exam_type not in valid_types:
        exam_type = ''

    document = exams.issue_document(
        ExamDocument.KIND_HALL_TICKET, profile, profile.semester, exam_type, request.user)
    data = exams.hall_ticket_data(profile, profile.semester, exam_type, document, request)
    content = pdf.hall_ticket_pdf(data)
    exams.record_download(document)
    log_action(request, 'exam.hall_ticket', document,
               detail=f'registration={profile.registration_number} code={document.verification_code}')
    filename = f'hall-ticket-{profile.registration_number}.pdf'
    return _pdf_response(content, filename)


@login_required(login_url='/login/')
@require_GET
def student_marksheet(request):
    """The student's own marksheet (?semester=3 defaults to the latest published)."""
    profile = _student_profile(request)
    if profile is None:
        messages.error(request, "No student profile is linked to this account.")
        return redirect('student_login')

    semester = request.GET.get('semester', '').strip()
    semester = int(semester) if semester.isdigit() else None
    document = exams.issue_document(
        ExamDocument.KIND_MARKSHEET, profile, semester or exams.latest_semester(profile), '', request.user)
    data = exams.marksheet_data(profile, semester, document, request)
    content = pdf.marksheet_pdf(data)
    exams.record_download(document)
    log_action(request, 'exam.marksheet', document,
               detail=f'registration={profile.registration_number} semester={data["semester"]} '
                      f'code={document.verification_code}')
    filename = f'marksheet-{profile.registration_number}-sem{data["semester"] or "all"}.pdf'
    return _pdf_response(content, filename)


@login_required(login_url='/login/')
@require_GET
def exam_documents(request):
    """One page listing the documents this student may download."""
    profile = _student_profile(request)
    if profile is None:
        messages.error(request, "No student profile is linked to this account.")
        return redirect('student_login')

    mine = (ExamDocument.objects.filter(student=profile, is_valid=True)
            .select_related('student').order_by('-issued_at')[:20])
    semesters = sorted({row['semester'] for row in exams._rows_for(profile)})
    return render(request, 'student/exam_documents.html', {
        'profile': profile,
        'documents': mine,
        'semesters': semesters,
        'latest_semester': exams.latest_semester(profile),
        'exam_types': ExamSchedule.EXAM_TYPE_CHOICES,
        'has_upcoming_exams': ExamSchedule.objects.filter(
            branch=profile.branch, semester=profile.semester, is_active=True,
            exam_date__gte=timezone.localdate()).exists(),
    })


# ── staff / teacher side ────────────────────────────────────────────────
@login_required(login_url='/login/')
@require_GET
def admin_exam_documents(request):
    """Pick a class + semester, then generate every document as one ZIP."""
    if not exams.is_exam_staff(request.user):
        return HttpResponseForbidden('Not allowed')

    branch = request.GET.get('branch', '').strip()
    semester = request.GET.get('semester', '').strip()
    semester_value = int(semester) if semester.isdigit() else None

    allowed = exams.teacher_classes(request.user)
    branches = [code for code, _label in StudentProfile.BRANCH_CHOICES]
    if not request.user.is_staff:
        branches = sorted({code for code, _sem in allowed if code})

    students = []
    if branch and semester_value and (request.user.is_staff
                                      or (branch, semester_value) in allowed):
        students = list(exams.students_for_class(branch, semester_value))

    return render(request, 'admin_dashboard/exam_documents.html', {
        'branches': branches,
        'semesters': list(range(1, 7)),
        'exam_types': ExamSchedule.EXAM_TYPE_CHOICES,
        'branch': branch,
        'semester': semester_value,
        'students': students,
        'is_admin': request.user.is_staff,
        'generated': (ExamDocument.objects.filter(kind=ExamDocument.KIND_HALL_TICKET)
                      .count()),
    })


@login_required(login_url='/login/')
@require_POST
def admin_exam_documents_bulk(request):
    """Generate one ZIP with a PDF per student. Hall tickets or marksheets."""
    if not exams.is_exam_staff(request.user):
        return HttpResponseForbidden('Not allowed')

    kind = request.POST.get('kind', ExamDocument.KIND_HALL_TICKET)
    if kind not in {ExamDocument.KIND_HALL_TICKET, ExamDocument.KIND_MARKSHEET}:
        return HttpResponseForbidden('Unknown document type')

    branch = request.POST.get('branch', '').strip()
    semester_raw = request.POST.get('semester', '').strip()
    semester = int(semester_raw) if semester_raw.isdigit() else None
    exam_type = request.POST.get('exam_type', '').strip()

    if not branch or not semester:
        messages.error(request, "Choose a branch and a semester first.")
        return redirect('admin_exam_documents')

    if not (request.user.is_staff or (branch, semester) in exams.teacher_classes(request.user)):
        return HttpResponseForbidden('Not your class')

    students = list(exams.students_for_class(branch, semester)[:BULK_LIMIT])
    if not students:
        messages.warning(request, "No students in that class yet.")
        return redirect(f"{reverse('admin_exam_documents')}?branch={branch}&semester={semester}")

    buffer = io.BytesIO()
    issues = 0
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for student in students:
            document = exams.issue_document(kind, student, semester, exam_type, request.user)
            if kind == ExamDocument.KIND_HALL_TICKET:
                data = exams.hall_ticket_data(student, semester, exam_type, document, request)
                content = pdf.hall_ticket_pdf(data)
                name = f'hall-ticket-{student.registration_number}.pdf'
            else:
                data = exams.marksheet_data(student, semester, document, request)
                content = pdf.marksheet_pdf(data)
                name = f'marksheet-{student.registration_number}-sem{semester}.pdf'
            bundle.writestr(name, content)
            issues += 1

    log_action(request, 'exam.bulk_generate', detail=(
        f'kind={kind} branch={branch} semester={semester} exam_type={exam_type or "-"} '
        f'students={issues}'))
    logger.info('bulk %s zip for %s sem %s: %s students', kind, branch, semester, issues)

    filename = f'{kind.lower()}-{branch}-sem{semester}-{timezone.localdate():%Y%m%d}.zip'
    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'private, no-store'
    return response


# ── download by code + public verification ─────────────────────────────
@login_required(login_url='/login/')
@require_GET
def download_exam_document(request, code):
    """Download an issued document by its code, if the caller may see that student."""
    document = get_object_or_404(ExamDocument, verification_code=code, is_valid=True)
    if not exams.can_view_document(request.user, document):
        log_action(request, 'exam.download_denied', document,
                   detail=f'code={code} user={request.user.username}')
        return HttpResponseForbidden('Not allowed')

    if document.kind == ExamDocument.KIND_HALL_TICKET:
        data = exams.hall_ticket_data(document.student, document.semester,
                                      document.exam_type, document, request)
        content = pdf.hall_ticket_pdf(data)
        filename = f'hall-ticket-{document.student.registration_number}.pdf'
    else:
        data = exams.marksheet_data(document.student, document.semester, document, request)
        content = pdf.marksheet_pdf(data)
        filename = f'marksheet-{document.student.registration_number}-sem{document.semester or "all"}.pdf'

    exams.record_download(document)
    log_action(request, 'exam.download', document,
               detail=f'code={code} kind={document.kind} by={request.user.username}')
    return _pdf_response(content, filename)


@require_GET
def verify_exam_document(request, code):
    """Public check: was this document issued here, and is it still valid?

    Deliberately shows no marks and a masked name, so a shared code cannot leak a
    student's result to whoever holds the paper.
    """
    document = ExamDocument.objects.filter(verification_code=code).select_related(
        'student', 'student__user').first()
    context = {
        'code': code,
        'document': document,
        'valid': bool(document and document.is_valid),
        'masked_name': None,
        'masked_registration': None,
        'exam_label': '',
    }
    if document:
        name_parts = (document.student.name or '').split()
        context['masked_name'] = (
            f"{name_parts[0]} {name_parts[-1][0]}." if len(name_parts) > 1
            else (name_parts[0] if name_parts else '—'))
        reg = document.student.registration_number or ''
        context['masked_registration'] = reg[:3] + '*' * max(0, len(reg) - 5) + reg[-2:] if len(reg) > 5 else reg
        if document.exam_type:
            context['exam_label'] = dict(ExamSchedule.EXAM_TYPE_CHOICES).get(
                document.exam_type, document.exam_type)
    return render(request, 'student/exam_verify.html', context)
