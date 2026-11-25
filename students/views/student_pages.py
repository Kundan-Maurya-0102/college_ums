"""Read-only student pages that the dashboard and sidebar link to.

These exist so every menu item has a real backend (no `href="#"`). Each one shows only
the signed-in student's own rows — the student id never comes from the URL — and each
one degrades to an empty state rather than an error.
"""
from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .. import exams
from ..models import (
    Assignment,
    Attendance,
    ClassSchedule,
    Notice,
    SemesterResult,
    StudyMaterial,
    Subject,
)

WEEKDAYS = OrderedDict([
    (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
    (4, 'Friday'), (5, 'Saturday'),
])


def _profile_or_redirect(request):
    profile = getattr(request.user, 'studentprofile', None)
    if profile is None:
        messages.error(request, "No student profile is linked to this account.")
    return profile


def _subjects(profile):
    if not (profile.branch and profile.semester):
        return Subject.objects.none()
    return Subject.objects.filter(branch=profile.branch, semester=profile.semester,
                                  is_active=True).order_by('subject_code')


@login_required(login_url='/login/')
@require_GET
def student_attendance(request):
    profile = _profile_or_redirect(request)
    if profile is None:
        return redirect('student_login')

    subjects = list(_subjects(profile))
    subject_ids = [s.pk for s in subjects]
    stats = {}
    if subject_ids:
        for row in (Attendance.objects.filter(student=profile, subject_id__in=subject_ids)
                    .values('subject_id')
                    .annotate(total=Count('id'), present=Count('id', filter=Q(is_present=True)))):
            stats[row['subject_id']] = row

    rows = []
    held_total = attended_total = 0
    for subject in subjects:
        row = stats.get(subject.pk, {})
        total, present = row.get('total', 0), row.get('present', 0)
        held_total += total
        attended_total += present
        percent = round(present / total * 100, 1) if total else None
        rows.append({
            'subject': subject, 'held': total, 'attended': present,
            'absent': total - present, 'percent': percent,
            'state': ('none' if percent is None else
                      'ok' if percent >= 75 else 'watch' if percent >= 60 else 'low'),
        })

    overall = round(attended_total / held_total * 100, 1) if held_total else None
    recent_absences = (Attendance.objects.filter(student=profile, is_present=False)
                       .select_related('subject').order_by('-date')[:10])
    return render(request, 'student/attendance.html', {
        'profile': profile,
        'rows': rows,
        'overall': overall,
        'held': held_total,
        'attended': attended_total,
        'recent_absences': recent_absences,
    })


@login_required(login_url='/login/')
@require_GET
def student_results(request):
    profile = _profile_or_redirect(request)
    if profile is None:
        return redirect('student_login')

    results = (SemesterResult.objects.filter(student=profile)
               .select_related('subject').order_by('semester', 'subject__subject_code'))
    by_semester = OrderedDict()
    for result in results:
        by_semester.setdefault(result.semester, []).append(result)

    semesters = []
    for semester, rows in by_semester.items():
        points = [{'credits': r.subject.credits or 0, 'point': exams.grade_point(r.grade),
                   'is_pass': r.is_pass} for r in rows]
        semesters.append({
            'semester': semester,
            'rows': rows,
            'credits': sum(p['credits'] for p in points),
            'sgpa': exams.gpa(points),
            'backlogs': sum(1 for p in points if not p['is_pass']),
        })

    all_points = [{'credits': r.subject.credits or 0, 'point': exams.grade_point(r.grade),
                   'is_pass': r.is_pass} for r in results]
    return render(request, 'student/results.html', {
        'profile': profile,
        'semesters': semesters,
        'cgpa': exams.gpa(all_points),
        'has_results': bool(semesters),
    })


@login_required(login_url='/login/')
@require_GET
def student_timetable(request):
    profile = _profile_or_redirect(request)
    if profile is None:
        return redirect('student_login')

    subjects = _subjects(profile)
    slots = (ClassSchedule.objects.filter(subject__in=subjects, is_active=True)
             .select_related('subject', 'faculty')
             .order_by('weekday', 'start_time'))
    grouped = OrderedDict((day, []) for day in WEEKDAYS)
    all_slots = list(slots)
    for slot in all_slots:
        grouped.setdefault(slot.weekday, []).append(slot)

    today = timezone.localdate().weekday()
    week = [{'index': day, 'name': name, 'slots': grouped.get(day, []),
             'is_today': day == today} for day, name in WEEKDAYS.items()]
    return render(request, 'student/timetable.html', {
        'profile': profile,
        'week': week,
        'today': today,
        'has_slots': bool(all_slots),
    })


@login_required(login_url='/login/')
@require_GET
def student_notices(request):
    profile = _profile_or_redirect(request)
    if profile is None:
        return redirect('student_login')

    seen_at = profile.dashboard_seen_at
    entries = []
    for notice in (Notice.objects.filter(is_active=True)
                   .select_related('created_by').order_by('-created_at')[:80]):
        if not notice.is_for_student(profile):
            continue
        entries.append({
            'notice': notice,
            'targeted': bool(notice.target_branches or notice.target_semesters),
            'unread': bool(seen_at is None or notice.created_at > seen_at),
        })

    return render(request, 'student/notices.html', {
        'profile': profile,
        'entries': entries,
        'unread': sum(1 for entry in entries if entry['unread']),
    })


@login_required(login_url='/login/')
@require_GET
def student_materials(request):
    profile = _profile_or_redirect(request)
    if profile is None:
        return redirect('student_login')

    subjects = list(_subjects(profile))
    materials = (StudyMaterial.objects.filter(subject__in=subjects, is_active=True)
                 .select_related('subject', 'uploaded_by').order_by('-created_at'))
    assignments = (Assignment.objects.filter(subject__in=subjects, is_active=True)
                   .select_related('subject', 'assigned_by').order_by('-created_at'))

    grouped = OrderedDict()
    for subject in subjects:
        grouped[subject] = {'materials': [], 'assignments': []}
    for material in materials:
        grouped[material.subject]['materials'].append(material)
    for assignment in assignments:
        grouped[assignment.subject]['assignments'].append(assignment)

    today = timezone.localdate()
    return render(request, 'student/materials.html', {
        'profile': profile,
        'grouped': grouped,
        'has_any': bool(materials or assignments),
        'today': today,
    })
