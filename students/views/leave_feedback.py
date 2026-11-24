"""Student leave applications and faculty feedback reports."""

from django.contrib import messages
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import (
    Feedback,
    LeaveApplication,
    StudentProfile,
)
from ..pagination import paginate
from .common import _int_or_none, admin_required


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

    # Summary stats (over the full filtered set, before pagination)
    avg_rating = feedbacks.aggregate(avg=Avg('rating'))['avg'] or 0
    total_count = feedbacks.count()
    page_obj = paginate(request, feedbacks)

    return render(request, 'admin_dashboard/feedback_report.html', {
        'page_obj': page_obj,
        'avg_rating': round(avg_rating, 1),
        'total_count': total_count,
        'branch': branch,
        'semester': semester,
        'branch_choices': StudentProfile.BRANCH_CHOICES,
    })

