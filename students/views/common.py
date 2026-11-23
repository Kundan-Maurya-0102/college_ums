"""Helpers shared by every view module: role checks, decorators, health probe."""
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


def is_admin(user):
    if not (user.is_authenticated and user.is_staff):
        return False
    if user.is_superuser:
        return True
    return not hasattr(user, "facultyprofile")


def is_teacher(user):
    return (
        user.is_authenticated
        and user.is_staff
        and hasattr(user, "facultyprofile")
        and user.facultyprofile.is_active
    )


def admin_required(view_func):
    decorated = login_required(user_passes_test(is_admin, login_url='/login/')(view_func))
    return decorated


def teacher_required(view_func):
    decorated = login_required(user_passes_test(is_teacher, login_url='/login/')(view_func))
    return decorated


def _int_or_none(value):
    """Return an int for valid form/query values, otherwise None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _date_or_today(value):
    """Parse an ISO date from a query/form value, falling back to today."""
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.date.today()


def _faculty_subjects(user):
    return user.facultyprofile.subjects.filter(is_active=True).order_by("branch", "semester", "subject_code")


def _subject_class_students(subject):
    return StudentProfile.objects.filter(branch=subject.branch, semester=subject.semester).order_by("registration_number")


def healthz(request):
    """Liveness probe for Docker/Caddy. No DB access, no auth, not visit-logged."""
    return JsonResponse({"status": "ok"})

