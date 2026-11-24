"""CSV bulk import upload and upload history."""
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

from ..audit import log_action
from ..pagination import paginate
from .common import *  # noqa: F401,F403
from .common import (_int_or_none, _date_or_today, _faculty_subjects,
                     _subject_class_students)


@admin_required
def csv_upload(request):
    result = None
    form = CSVUploadForm()

    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.uploaded_by = request.user.get_full_name() or request.user.username
            upload.save()

            result = process_any_csv_upload(upload)
            # Save generic counters for any dataset type
            upload.is_processed = True
            upload.records_created = int(result.get("created", 0) or 0)
            upload.records_updated = int(result.get("updated", 0) or 0)
            upload.errors = "\n".join(result.get("errors", []) or [])
            upload.save()
            log_action(request, "csv.import", upload,
                       detail=f"created={upload.records_created} updated={upload.records_updated} errors={len(result.get('errors', []) or [])}")

            messages.success(
                request,
                f"✅ CSV processed: {result['created']} created, {result['updated']} updated, "
                f"{len(result['errors'])} errors."
            )
        else:
            messages.error(request, "❌ Form validation failed. Please check the file.")

    return render(request, 'admin_dashboard/upload_csv.html', {
        'form': form,
        'result': result,
    })


@admin_required
def upload_history(request):
    uploads = paginate(request, CSVUpload.objects.all())
    return render(request, 'admin_dashboard/upload_history.html', {'uploads': uploads})

