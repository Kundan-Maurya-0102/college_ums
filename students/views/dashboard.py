"""Admin, teacher and reports dashboards."""
import datetime
import hashlib

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from .. import teacher_data
from ..models import (
    Attendance,
    CSVUpload,
    FacultyProfile,
    FeePayment,
    LeaveApplication,
    Notice,
    StudentProfile,
    Subject,
    WebsiteVisit,
)
from .common import admin_required, teacher_required


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
    """What needs the teacher today — aggregated in teacher_data, not per student."""
    faculty = request.user.facultyprofile
    data = teacher_data.build(faculty)

    notice_rows = [{"notice": notice, "unread": False} for notice in data["notices"]]
    context = {
        "faculty": faculty,
        # role-agnostic keys the shared shell reads
        "announcements": notice_rows,
        "messages": [],
        "unread_count": 0,
        "show_dark_toggle": True,
        "query": (request.GET.get("q") or "").strip()[:60],
        # the dashboard itself
        **data,
        "subjects": [row["subject"] for row in data["subject_rows"]],
        "student_count": data["student_count"],
        "classes_taken": data["classes_held"],
        "avg_attendance": (round(sum(row["percent"] for row in data["subject_rows"]
                                     if row["percent"] is not None)
                                 / len([row for row in data["subject_rows"]
                                        if row["percent"] is not None]), 1)
                           if any(row["percent"] is not None for row in data["subject_rows"]) else 0),
        "low_attendance": [{"student": item["student"], "subject": item["subject"],
                            "percentage": item["percent"]} for item in data["at_risk"]],
    }
    return render(request, "teacher/dashboard.html", context)


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
    cache_key = "reports:v1:" + hashlib.md5(str(signature).encode(), usedforsecurity=False).hexdigest()

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

