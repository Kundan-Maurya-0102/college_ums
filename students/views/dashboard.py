"""Admin, teacher and reports dashboards."""
import hashlib
import csv
import datetime
import io

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.cache import cache
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

from .common import *  # noqa: F401,F403
from .common import (_int_or_none, _date_or_today, _faculty_subjects,
                     _subject_class_students)


@admin_required
def admin_dashboard(request):
    cache_seconds = getattr(settings, "DASHBOARD_CACHE_SECONDS", 0)
    if cache_seconds:
        cached = cache.get("dashboard:admin:v1")
        if cached is not None:
            return render(request, 'admin_dashboard/index.html', cached)

    total_students = StudentProfile.objects.count()
    branch_names = dict(StudentProfile.BRANCH_CHOICES)
    branch_stats = {
        branch_names.get(row["branch"], row["branch"]): row["count"]
        for row in StudentProfile.objects.values("branch")
        .annotate(count=Count("id")).order_by("branch")
    }

    recent_uploads = CSVUpload.objects.order_by('-upload_date')[:5]
    recent_students = StudentProfile.objects.select_related("user").order_by('-created_at')[:8]
    total_notices = Notice.objects.filter(is_active=True).count()
    total_subjects = Subject.objects.filter(is_active=True).count()
    total_teachers = FacultyProfile.objects.filter(is_active=True).count()
    attendance_totals = Attendance.objects.aggregate(
        total=Count("id"), present=Count("id", filter=Q(is_present=True)))
    total_attendance = attendance_totals["total"] or 0
    present_attendance = attendance_totals["present"] or 0
    attendance_average = round((present_attendance / total_attendance) * 100, 1) if total_attendance else 0
    visit_stats = WebsiteVisit.objects.aggregate(
        total=Count("id"),
        today=Count("id", filter=Q(visited_at__date=datetime.date.today())),
        seconds=Sum("duration_seconds"),
    )
    total_visits = visit_stats["total"] or 0
    today_visits = visit_stats["today"] or 0
    total_visit_minutes = round((visit_stats["seconds"] or 0) / 60, 1)

    # One grouped query instead of two queries per student.
    attendance_stats = (Attendance.objects.values("student_id")
                        .annotate(total=Count("id"),
                                  present=Count("id", filter=Q(is_present=True))))
    risky = []
    for row in attendance_stats:
        if not row["total"]:
            continue
        pct = round(row["present"] / row["total"] * 100, 1)
        if pct < 75:
            risky.append((row["student_id"], pct))
    risky.sort(key=lambda item: item[1])
    risky = risky[:8]
    profiles = StudentProfile.objects.in_bulk([student_id for student_id, _ in risky])
    low_attendance_students = [
        {"student": profiles[student_id], "percentage": pct}
        for student_id, pct in risky if student_id in profiles
    ]

    context = {
        'total_students': total_students,
        'branch_stats': branch_stats,
        'recent_uploads': recent_uploads,
        'recent_students': recent_students,
        'total_notices': total_notices,
        'total_subjects': total_subjects,
        'total_teachers': total_teachers,
        'attendance_average': attendance_average,
        'total_visits': total_visits,
        'today_visits': today_visits,
        'total_visit_minutes': total_visit_minutes,
        'low_attendance_students': low_attendance_students,
    }
    if cache_seconds:
        cache.set("dashboard:admin:v1", context, cache_seconds)
    return render(request, 'admin_dashboard/index.html', context)


@teacher_required
def teacher_dashboard(request):
    faculty = request.user.facultyprofile
    subjects = list(_faculty_subjects(request.user))
    attendance_qs = Attendance.objects.filter(subject__in=subjects)
    classes_taken = attendance_qs.values("subject_id", "date").distinct().count()
    total_marks = InternalExam.objects.filter(subject__in=subjects).count()

    total_records = attendance_qs.count()
    present_records = attendance_qs.filter(is_present=True).count()
    avg_attendance = round((present_records / total_records) * 100, 1) if total_records else 0

    class_filter = Q()
    for subject in subjects:
        class_filter |= Q(branch=subject.branch, semester=subject.semester)
    class_students = (StudentProfile.objects.filter(class_filter) if subjects
                      else StudentProfile.objects.none())
    student_ids = set(class_students.values_list("id", flat=True))

    # Single grouped query for subject-wise attendance instead of N+1 lookups.
    pair_stats = (attendance_qs.values("student_id", "subject_id")
                  .annotate(total=Count("id"), present=Count("id", filter=Q(is_present=True))))
    risky = []
    for row in pair_stats:
        if not row["total"]:
            continue
        pct = round(row["present"] / row["total"] * 100, 1)
        if pct < 75:
            risky.append((row["student_id"], row["subject_id"], pct))
    risky.sort(key=lambda item: item[2])
    risky = risky[:8]
    students_by_id = StudentProfile.objects.in_bulk({item[0] for item in risky})
    subjects_by_id = {subject.id: subject for subject in subjects}
    low_attendance = [
        {"student": students_by_id[sid], "subject": subjects_by_id[sub_id], "percentage": pct}
        for sid, sub_id, pct in risky
        if sid in students_by_id and sub_id in subjects_by_id
    ]

    high_marks = InternalExam.objects.filter(subject__in=subjects).select_related("student", "subject").order_by("-marks_obtained")[:8]
    schedules = ClassSchedule.objects.filter(faculty=faculty, is_active=True).select_related("subject")[:8]

    return render(request, "teacher/dashboard.html", {
        "faculty": faculty,
        "subjects": subjects,
        "classes_taken": classes_taken,
        "student_count": len(student_ids),
        "avg_attendance": avg_attendance,
        "total_marks": total_marks,
        "low_attendance": low_attendance,
        "high_marks": high_marks,
        "schedules": schedules,
    })


@admin_required
def reports_view(request):
    cache_seconds = getattr(settings, "REPORTS_CACHE_SECONDS", 0)
    signature = (
        StudentProfile.objects.count(),
        Attendance.objects.count(),
        FeePayment.objects.count(),
        LeaveApplication.objects.count(),
        FacultyProfile.objects.count(),
        Subject.objects.count(),
    )
    cache_key = "reports:v1:" + hashlib.md5(str(signature).encode()).hexdigest()

    if cache_seconds:
        cached = cache.get(cache_key)
        if cached is not None:
            return render(request, 'admin_dashboard/reports.html', cached)

    total_students = StudentProfile.objects.count()
    total_teachers = FacultyProfile.objects.filter(is_active=True).count()
    total_subjects = Subject.objects.filter(is_active=True).count()

    # Branch-wise student count (single grouped query)
    branch_names = dict(StudentProfile.BRANCH_CHOICES)
    branch_data = {
        branch_names.get(row["branch"], row["branch"]): row["count"]
        for row in StudentProfile.objects.values("branch")
        .annotate(count=Count("id")).order_by("branch")
    }

    # Attendance defaulters (< 75%) using one grouped query
    attendance_stats = (Attendance.objects.values("student_id")
                        .annotate(total=Count("id"),
                                  present=Count("id", filter=Q(is_present=True))))
    risky = []
    for row in attendance_stats:
        if not row["total"]:
            continue
        pct = round(row["present"] / row["total"] * 100, 1)
        if pct < 75:
            risky.append((row["student_id"], pct))
    risky.sort(key=lambda item: item[1])
    risky = risky[:20]
    profiles = StudentProfile.objects.in_bulk([student_id for student_id, _ in risky])
    defaulters = [
        {"student": profiles[student_id], "percentage": pct}
        for student_id, pct in risky if student_id in profiles
    ]

    # Fee collection summary
    total_fees_collected = FeePayment.objects.filter(status='PAID').aggregate(total=Sum('amount_paid'))['total'] or 0
    pending_leaves = LeaveApplication.objects.filter(status='PENDING').count()

    context = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_subjects': total_subjects,
        'branch_data': branch_data,
        'defaulters': defaulters[:20],
        'total_fees_collected': total_fees_collected,
        'pending_leaves': pending_leaves,
    }
    if cache_seconds:
        cache.set(cache_key, context, cache_seconds)
    return render(request, 'admin_dashboard/reports.html', context)

