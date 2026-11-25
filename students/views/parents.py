"""Parent / guardian portal: read-only view of a guardian's own children.

Scope is intentionally small (release candidate): attendance %, latest marks, fee
position and notices for each linked child. Everything is scoped by the guardian's
own `students` relation, so a guessed student id returns 404 rather than another
family's data.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from ..models import Attendance, FeePayment, GuardianProfile, InternalExam, Notice, StudentProfile


def guardian_for(user):
    """Return the guardian profile for `user`, or None (never raises)."""
    if not user.is_authenticated:
        return None
    return GuardianProfile.objects.filter(user=user, is_active=True).first()


def _owned_child(request, pk):
    """Get one of *this guardian's* children, or 404 — never another family's child."""
    guardian = getattr(request, 'guardian', None)
    if guardian is None:
        raise Http404("No guardian profile")
    return get_object_or_404(StudentProfile, pk=pk, guardians=guardian)


def _attendance_percent(student):
    stats = Attendance.objects.filter(student=student).aggregate(
        total=Count('id'), present=Count('id', filter=Q(is_present=True)))
    total = stats['total'] or 0
    if not total:
        return None
    return round(stats['present'] / total * 100, 1)


def _fee_position(student):
    paid = FeePayment.objects.filter(student=student).aggregate(total=Sum('amount_paid'))
    return {'paid': paid['total'] or 0}


def _latest_marks(student):
    return (InternalExam.objects.filter(student=student)
            .select_related('subject').order_by('-exam_date')[:10])


@login_required
@require_GET
def parent_dashboard(request):
    request.guardian = guardian_for(request.user)
    if request.guardian is None:
        messages.error(request, "This account is not linked to a student. Please contact the office.")
        return redirect('student_login')

    children = []
    for child in request.guardian.children():
        children.append({
            'student': child,
            'attendance': _attendance_percent(child),
            'fees': _fee_position(child),
        })

    notices = (Notice.objects.filter(is_active=True)
               .select_related('created_by').order_by('-created_at')[:5])
    return render(request, 'parent/dashboard.html', {
        'guardian': request.guardian,
        'children': children,
        'notices': notices,
    })


@login_required
@require_GET
def parent_child(request, pk):
    request.guardian = guardian_for(request.user)
    child = _owned_child(request, pk)
    return render(request, 'parent/child.html', {
        'guardian': request.guardian,
        'student': child,
        'attendance': _attendance_percent(child),
        'payments': FeePayment.objects.filter(student=child).select_related('fee_structure')[:20],
        'marks': _latest_marks(child),
        'notices': Notice.objects.filter(is_active=True).order_by('-created_at')[:5],
    })
