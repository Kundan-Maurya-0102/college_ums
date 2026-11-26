"""Admin, teacher and reports dashboards."""
import datetime
import hashlib

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from .. import admin_data, teacher_data
from ..models import (
    Attendance,
    FacultyProfile,
    FeePayment,
    LeaveApplication,
    StudentProfile,
    Subject,
)
from .common import admin_required, teacher_required


@admin_required
def admin_dashboard(request):
    """One aggregate bundle (students/admin_data.py) plus the cached shell context."""
    cache_seconds = getattr(settings, "DASHBOARD_CACHE_SECONDS", 0)
    if cache_seconds:
        cached = cache.get("dashboard:admin:v1")
        if cached is not None:
            return render(request, 'admin_dashboard/index.html', cached)

    context = {
        **admin_data.build(),
        'today': datetime.date.today(),
        'show_dark_toggle': True,
        'unread_count': 0,
        'query': (request.GET.get('q') or '').strip()[:60],
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

