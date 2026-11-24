"""Super Admin (platform owner) panel.

Access is limited to superusers and members of the "Platform Admin" group via
``platform_admin_required``; every view also logs to the audit trail.
"""
import csv
import io
import json
import secrets
from functools import wraps

from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from students.audit import log_action
from students.pagination import paginate

from .forms import CollegeForm, PlanForm, TicketForm, TicketReplyForm
from .models import College, Plan, SupportTicket, UsageSnapshot, platform_admin_required


def platform_admin_required_view(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())
        if not platform_admin_required(request.user):
            return render(request, "platform_admin/forbidden.html", status=403)
        return view(request, *args, **kwargs)

    return wrapper


# ── overview ──────────────────────────────────────────────────────────

@platform_admin_required_view
def overview(request):
    today = timezone.localdate()
    colleges = College.objects.all()
    stats = {
        "colleges": colleges.count(),
        "active": colleges.filter(status=College.STATUS_ACTIVE).count(),
        "trial": colleges.filter(status=College.STATUS_TRIAL).count(),
        "suspended": colleges.filter(status=College.STATUS_SUSPENDED).count(),
        "students": colleges.aggregate(total=Sum("student_count"))["total"] or 0,
        "storage_mb": round((colleges.aggregate(total=Sum("storage_bytes"))["total"] or 0)
                            / (1024 * 1024), 1),
        "open_tickets": SupportTicket.objects.filter(status=SupportTicket.STATUS_OPEN).count(),
    }
    expiring = (colleges.exclude(status=College.STATUS_SUSPENDED)
                .filter(subscription_expires_on__isnull=False,
                        subscription_expires_on__lte=today + timezone.timedelta(days=30))
                .order_by("subscription_expires_on"))
    recent_tickets = SupportTicket.objects.select_related("college")[:8]
    return render(request, "platform_admin/overview.html", {
        "stats": stats,
        "expiring": expiring,
        "recent_tickets": recent_tickets,
        "active_nav": "overview",
    })


# ── colleges ──────────────────────────────────────────────────────────

@platform_admin_required_view
def college_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    colleges = College.objects.select_related("plan")
    if query:
        colleges = colleges.filter(Q(name__icontains=query) | Q(slug__icontains=query)
                                   | Q(domain__icontains=query))
    if status:
        colleges = colleges.filter(status=status)
    page_obj = paginate(request, colleges, per_page=20)
    return render(request, "platform_admin/college_list.html", {
        "page_obj": page_obj,
        "colleges": page_obj.object_list,
        "query": query,
        "status": status,
        "status_choices": College.STATUS_CHOICES,
        "active_nav": "colleges",
    })


@platform_admin_required_view
def college_create(request):
    form = CollegeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        college = form.save()
        log_action(request, "platform.college.create", obj=college,
                   detail=college.name)
        messages.success(request, f"{college.name} added.")
        return redirect("platform:college_detail", pk=college.pk)
    return render(request, "platform_admin/college_form.html",
                  {"form": form, "title": "Add college", "active_nav": "colleges"})


@platform_admin_required_view
def college_detail(request, pk):
    college = get_object_or_404(College.objects.select_related("plan"), pk=pk)
    form = CollegeForm(request.POST or None, instance=college)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "platform.college.update", obj=college,
                   detail=college.name)
        messages.success(request, "College updated.")
        return redirect("platform:college_detail", pk=college.pk)

    usage = college.usage.all()[:30]
    tickets = college.tickets.all()[:10]
    return render(request, "platform_admin/college_detail.html", {
        "college": college,
        "form": form,
        "usage": usage,
        "tickets": tickets,
        "active_nav": "colleges",
    })


@platform_admin_required_view
def college_suspend(request, pk):
    college = get_object_or_404(College, pk=pk)
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    college.suspend(reason=request.POST.get("reason", "suspended by platform admin"))
    log_action(request, "platform.college.suspend", obj=college,
               detail=college.name)
    messages.warning(request, f"{college.name} suspended — its deployment is read-only.")
    return redirect("platform:college_detail", pk=college.pk)


@platform_admin_required_view
def college_resume(request, pk):
    college = get_object_or_404(College, pk=pk)
    if request.method != "POST":
        return HttpResponseForbidden("POST required")
    college.resume()
    log_action(request, "platform.college.resume", obj=college,
               detail=college.name)
    messages.success(request, f"{college.name} resumed ({college.get_status_display()}).")
    return redirect("platform:college_detail", pk=college.pk)


@platform_admin_required_view
def college_backup(request, pk):
    """One-click download of the college's latest backup metadata / file.

    Backups live on the college deployment host, so the platform stores the path
    and streams the file when the platform and college share a volume (or when
    the college mirrors its backup to the platform host). Otherwise a JSON
    snapshot with the college's configuration + metrics is returned, which is
    enough for support/restore hand-offs.
    """
    college = get_object_or_404(College, pk=pk)
    log_action(request, "platform.college.backup_download", obj=college,
               detail=college.name)

    from pathlib import Path

    from django.conf import settings

    if college.backup_path:
        path = Path(college.backup_path)
        allowed_root = Path(getattr(settings, "PLATFORM_BACKUP_DIR", "/var/backups/ums"))
        try:
            path.resolve().relative_to(allowed_root.resolve())
            if path.is_file():
                payload = path.read_bytes()
                response = HttpResponse(payload, content_type="application/octet-stream")
                response["Content-Disposition"] = f'attachment; filename="{path.name}"'
                return response
        except (ValueError, OSError):
            pass  # outside the allowed dir or unreadable → fall back to snapshot

    snapshot = {
        "college": {
            "name": college.name,
            "slug": college.slug,
            "domain": college.domain,
            "status": college.status,
            "plan": college.plan.name if college.plan else None,
            "subscription_expires_on": str(college.subscription_expires_on or ""),
            "student_limit": college.effective_limit,
        },
        "metrics": {
            "student_count": college.student_count,
            "active_users_30d": college.active_users_30d,
            "storage_mb": college.storage_mb,
            "last_login_at": college.last_login_at.isoformat() if college.last_login_at else None,
            "reported_at": (college.metrics_reported_at.isoformat()
                            if college.metrics_reported_at else None),
        },
        "generated_at": timezone.now().isoformat(),
        "note": "Configuration snapshot. Database dump: see docs/BACKUP_RESTORE.md.",
    }
    response = HttpResponse(json.dumps(snapshot, indent=2), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{college.slug}-snapshot.json"'
    return response


# ── plans ─────────────────────────────────────────────────────────────

@platform_admin_required_view
def plan_list(request):
    plans = Plan.objects.annotate(college_count=Count("colleges"))
    return render(request, "platform_admin/plan_list.html",
                  {"plans": plans, "active_nav": "plans"})


@platform_admin_required_view
def plan_create(request):
    form = PlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        plan = form.save()
        log_action(request, "platform.plan.create", obj=plan, detail=plan.name)
        messages.success(request, f"Plan {plan.name} created.")
        return redirect("platform:plans")
    return render(request, "platform_admin/plan_form.html",
                  {"form": form, "title": "New plan", "active_nav": "plans"})


@platform_admin_required_view
def plan_edit(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    form = PlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "platform.plan.update", obj=plan, detail=plan.name)
        messages.success(request, "Plan updated.")
        return redirect("platform:plans")
    return render(request, "platform_admin/plan_form.html",
                  {"form": form, "title": f"Edit {plan.name}", "active_nav": "plans"})


# ── usage ─────────────────────────────────────────────────────────────

@platform_admin_required_view
def usage_report(request):
    colleges = College.objects.select_related("plan").order_by("-student_count")
    snapshots = (UsageSnapshot.objects.select_related("college")
                 .order_by("-day")[:100])
    if request.GET.get("format") == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["college", "slug", "plan", "status", "students", "limit",
                         "active_users_30d", "storage_mb", "last_login"])
        for college in colleges:
            writer.writerow([college.name, college.slug,
                             college.plan.name if college.plan else "",
                             college.status, college.student_count, college.effective_limit,
                             college.active_users_30d, college.storage_mb,
                             college.last_login_at.isoformat() if college.last_login_at else ""])
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="college-usage.csv"'
        return response
    totals = {
        "students": sum(c.student_count for c in colleges),
        "active": sum(c.active_users_30d for c in colleges),
        "storage_mb": round(sum(c.storage_bytes for c in colleges) / (1024 * 1024), 1),
    }
    return render(request, "platform_admin/usage.html", {
        "colleges": colleges,
        "snapshots": snapshots,
        "totals": totals,
        "active_nav": "usage",
    })


# ── support tickets ───────────────────────────────────────────────────

@platform_admin_required_view
def ticket_list(request):
    status = request.GET.get("status", "")
    tickets = SupportTicket.objects.select_related("college")
    if status:
        tickets = tickets.filter(status=status)
    page_obj = paginate(request, tickets, per_page=20)
    return render(request, "platform_admin/ticket_list.html", {
        "page_obj": page_obj,
        "tickets": page_obj.object_list,
        "status": status,
        "status_choices": SupportTicket.STATUS_CHOICES,
        "active_nav": "tickets",
    })


@platform_admin_required_view
def ticket_create(request):
    form = TicketForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ticket = form.save()
        log_action(request, "platform.ticket.create", obj=ticket,
                   detail=ticket.subject)
        messages.success(request, f"Ticket #{ticket.pk} created.")
        return redirect("platform:ticket_detail", pk=ticket.pk)
    return render(request, "platform_admin/ticket_form.html",
                  {"form": form, "title": "New ticket", "active_nav": "tickets"})


@platform_admin_required_view
def ticket_detail(request, pk):
    ticket = get_object_or_404(SupportTicket.objects.select_related("college"), pk=pk)
    form = TicketReplyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        reply = form.save(commit=False)
        reply.ticket = ticket
        reply.author = request.user.get_username()
        reply.from_platform = True
        reply.save()
        ticket.status = SupportTicket.STATUS_ANSWERED
        ticket.save(update_fields=["status", "updated_at"])
        log_action(request, "platform.ticket.reply", obj=ticket,
                   detail=ticket.subject)
        messages.success(request, "Reply sent to the college.")
        return redirect("platform:ticket_detail", pk=ticket.pk)

    if request.method == "POST" and request.POST.get("action") == "close":
        ticket.status = SupportTicket.STATUS_CLOSED
        ticket.save(update_fields=["status", "updated_at"])
        log_action(request, "platform.ticket.close", obj=ticket,
                   detail=ticket.subject)
        messages.info(request, f"Ticket #{ticket.pk} closed.")
        return redirect("platform:ticket_detail", pk=ticket.pk)

    return render(request, "platform_admin/ticket_detail.html", {
        "ticket": ticket,
        "replies": ticket.replies.all(),
        "form": form,
        "active_nav": "tickets",
    })


# ── machine-readable metrics (college deployments push here) ──────────

def _metrics_token_ok(request, college):
    """One token per college, so college A can never write college B's numbers.

    `College.metrics_token` wins when set. The old shared PLATFORM_METRICS_TOKEN is
    only accepted for a college that has no token yet (first report / setup).
    """
    from django.conf import settings

    presented = request.headers.get("X-Platform-Token", "")
    if not presented:
        return False
    if college.metrics_token:
        return secrets.compare_digest(presented, college.metrics_token)
    shared = getattr(settings, "PLATFORM_METRICS_TOKEN", "")
    return bool(shared) and secrets.compare_digest(presented, shared)


def metrics_endpoint(request, slug):
    """POST {"student_count":…, "active_users_30d":…, "storage_bytes":…} with the
    shared token from PLATFORM_METRICS_TOKEN. Kept token-only (no session) so a
    college deployment can report without a human login."""

    if request.method != "POST":
        return JsonResponse({"detail": "POST required"}, status=405)
    college = get_object_or_404(College, slug=slug)
    if not _metrics_token_ok(request, college):
        return JsonResponse({"detail": "forbidden"}, status=403)
    try:
        payload = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"detail": "invalid json"}, status=400)
    for field in ("student_count", "active_users_30d", "storage_bytes", "last_login_at"):
        if field in payload and payload[field] is not None:
            setattr(college, field, payload[field])
    college.metrics_reported_at = timezone.now()
    college.save()
    UsageSnapshot.objects.update_or_create(
        college=college, day=timezone.localdate(),
        defaults={
            "active_users": college.active_users_30d,
            "student_count": college.student_count,
            "messages_sent": int(payload.get("messages_sent", 0) or 0),
            "payments_count": int(payload.get("payments_count", 0) or 0),
            "api_calls": int(payload.get("api_calls", 0) or 0),
        })
    return JsonResponse({"ok": True, "college": college.slug})
