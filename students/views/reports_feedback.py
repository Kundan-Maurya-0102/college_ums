"""In-app bug / feedback reporting, available to every signed-in role."""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ..audit import log_action
from ..forms_public import BugReportForm
from ..models import BugReport
from ..security import rate_limit_hit

logger = logging.getLogger(__name__)


def _safe_next_url(request):
    """Return the user-supplied 'next' URL only if it is safe, else fallback."""
    url = request.POST.get('next', '') or ''
    if url and url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return url
    return 'help_center'


def _role_of(user):
    if getattr(user, 'studentprofile', None):
        return 'student'
    if getattr(user, 'facultyprofile', None) and not user.is_staff:
        return 'teacher'
    return 'admin'


@login_required
@require_POST
def report_problem(request):
    """Store a bug report and bounce back to the page the user came from."""
    next_url = _safe_next_url(request)

    if rate_limit_hit(request, 'bugreport', limit=5, window_seconds=600):
        messages.error(request, "Too many reports in a short time. Please try again in a few minutes.")
        return redirect(next_url)

    form = BugReportForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Could not send that: " + " ".join(
            error for errors in form.errors.values() for error in errors))
        return redirect(next_url)

    report = form.save(commit=False)
    report.user = request.user
    report.role = _role_of(request.user)
    report.page_url = (request.POST.get('page_url') or '')[:300]
    report.user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:300]
    report.save()
    log_action(request, 'bug_report', obj=report, detail=report.category)
    logger.info("bug report #%s from role=%s category=%s", report.pk, report.role, report.category)
    messages.success(request, "Thanks! Your report was sent to the college office.")
    return redirect(next_url)


@login_required
def bug_report_list(request):
    """Staff view of incoming reports."""
    if not (request.user.is_staff or request.user.is_superuser):
        return render(request, '403.html', status=403)
    status = request.GET.get('status', '')
    reports = BugReport.objects.select_related('user')
    if status in dict(BugReport.STATUS):
        reports = reports.filter(status=status)
    return render(request, 'admin_dashboard/bug_reports.html', {
        'reports': reports[:200],
        'status': status,
        'status_choices': BugReport.STATUS,
        'page_title': 'Bug reports',
    })


@login_required
@require_POST
def bug_report_update(request, pk):
    if not (request.user.is_staff or request.user.is_superuser):
        return render(request, '403.html', status=403)
    report = BugReport.objects.filter(pk=pk).first()
    if not report:
        messages.error(request, "Report not found.")
        return redirect('bug_report_list')
    status = request.POST.get('status')
    if status in dict(BugReport.STATUS):
        report.status = status
    report.admin_note = (request.POST.get('admin_note') or '')[:2000]
    report.save(update_fields=['status', 'admin_note'])
    log_action(request, 'bug_report_update', obj=report, detail=report.status)
    messages.success(request, "Report updated.")
    return redirect('bug_report_list')
