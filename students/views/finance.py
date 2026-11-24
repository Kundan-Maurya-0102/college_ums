"""Fee structure and fee payments."""
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
from ..audit import log_action
from ..models import (Assignment, Attendance, BannerImage, CSVUpload, ClassSchedule,
                     Doubt, DoubtReply, Event, ExamSchedule, FacultyProfile,
                     Feedback, FeePayment, FeeStructure, InternalExam,
                     LeaveApplication, Notice, SemesterResult, StudentProfile,
                     StudyMaterial, Subject, WebsiteVisit)

from .common import *  # noqa: F401,F403
from .common import (_int_or_none, _date_or_today, _faculty_subjects,
                     _subject_class_students)


@admin_required
def fee_structure_list(request):
    structures = FeeStructure.objects.all().order_by('branch', 'semester', 'fee_type')
    return render(request, 'admin_dashboard/fees.html', {'structures': structures})


@admin_required
def fee_structure_create(request):
    form = FeeStructureForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Fee structure created.")
        return redirect('fee_structure_list')
    return render(request, 'admin_dashboard/fee_form.html', {'form': form, 'action': 'Create'})


@admin_required
def fee_structure_edit(request, pk):
    structure = get_object_or_404(FeeStructure, pk=pk)
    form = FeeStructureForm(request.POST or None, instance=structure)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Fee structure updated.")
        return redirect('fee_structure_list')
    return render(request, 'admin_dashboard/fee_form.html', {'form': form, 'action': 'Edit', 'structure': structure})


@admin_required
def fee_structure_delete(request, pk):
    structure = get_object_or_404(FeeStructure, pk=pk)
    if request.method == 'POST':
        structure.delete()
        messages.success(request, "Fee structure deleted.")
        return redirect('fee_structure_list')
    return render(request, 'admin_dashboard/fee_delete_confirm.html', {'structure': structure})


@admin_required
def fee_payments(request):
    payments = FeePayment.objects.select_related('student', 'fee_structure').all()
    q = request.GET.get('q', '')
    if q:
        payments = payments.filter(
            Q(student__name__icontains=q) |
            Q(student__registration_number__icontains=q) |
            Q(receipt_number__icontains=q)
        )
    paginator = Paginator(payments, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_dashboard/fee_payments.html', {'page_obj': page_obj, 'q': q})


@admin_required
def fee_payment_create(request):
    form = FeePaymentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        payment = form.save(commit=False)
        payment.recorded_by = request.user.get_full_name() or request.user.username
        payment.save()
        log_action(request, "fee.payment.create", payment,
                   detail=f"{payment.student.registration_number} amount={payment.amount_paid} receipt={payment.receipt_number}")
        messages.success(request, f"Payment recorded: Receipt #{payment.receipt_number}")
        return redirect('fee_payments')
    return render(request, 'admin_dashboard/fee_payment_form.html', {'form': form})

