"""Student leave applications and faculty feedback reports."""
import csv
import datetime
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..ai_helper import get_ai_response
from ..upload_router import process_any_csv_upload
from ..password_links import build_set_password_link
from ..forms import (AssignmentForm, BannerImageForm, CSVUploadForm, ClassScheduleForm,
                    DoubtForm, DoubtReplyForm, EventForm, ExamScheduleForm,
                    FacultyProfileForm, FeedbackForm, FeePaymentForm,
                    FeeStructureForm, InternalExamForm, LeaveApplicationForm,
                    NoticeForm, StudentProfileForm, StudyMaterialForm, SubjectForm,
                    AdminUserForm)
from ..models import (Assignment, Attendance, BannerImage, CSVUpload, ClassSchedule,
                     Doubt, DoubtReply, Event, ExamSchedule, FacultyProfile,
                     Feedback, FeePayment, FeeStructure, InternalExam,
                     LeaveApplication, Notice, SemesterResult, StudentProfile,
                     StudyMaterial, Subject, WebsiteVisit)

from ..pagination import paginate
from .common import *  # noqa: F401,F403
from .common import (_int_or_none, _date_or_today, _faculty_subjects,
                     _subject_class_students)


@admin_required
def leave_applications(request):
    apps = LeaveApplication.objects.select_related('student', 'reviewed_by').all()
    status = request.GET.get('status', '')
    if status:
        apps = apps.filter(status=status)
    return render(request, 'admin_dashboard/leave_applications.html',
                  {'applications': paginate(request, apps), 'status_filter': status})


@admin_required
def leave_review(request, pk):
    app = get_object_or_404(LeaveApplication, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        remarks = request.POST.get('remarks', '')
        if action in ('APPROVED', 'REJECTED'):
            app.status = action
            app.reviewed_by = request.user
            app.reviewed_at = timezone.now()
            app.admin_remarks = remarks
            app.save()
            messages.success(request, f"Leave application {action.lower()}.")
        return redirect('leave_applications')
    return render(request, 'admin_dashboard/leave_review.html', {'application': app})


@admin_required
def feedback_report(request):
    feedbacks = Feedback.objects.select_related('student', 'subject', 'faculty').all()
    branch = request.GET.get('branch', '')
    semester = _int_or_none(request.GET.get('semester'))
    if branch:
        feedbacks = feedbacks.filter(subject__branch=branch)
    if semester:
        feedbacks = feedbacks.filter(semester=semester)

    # Summary stats
    avg_rating = feedbacks.aggregate(avg=Avg('rating'))['avg'] or 0
    total_count = feedbacks.count()

    return render(request, 'admin_dashboard/feedback_report.html', {
        'feedbacks': paginate(request, feedbacks),
        'avg_rating': round(avg_rating, 1),
        'total_count': total_count,
        'branch': branch,
        'semester': semester,
        'branch_choices': StudentProfile.BRANCH_CHOICES,
    })

