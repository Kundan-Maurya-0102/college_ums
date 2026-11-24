"""Public landing page + demo request (no login required)."""
import logging

from django.conf import settings
from django.shortcuts import redirect, render

from platform_admin.models import DemoRequest, Plan

from ..forms_public import DemoRequestForm

logger = logging.getLogger(__name__)


def landing_page(request):
    """Marketing page for a college that does not have the product yet.

    Signed-in users never see it — they are sent to their own dashboard.
    Disable with LANDING_PAGE_ENABLED=False (the root then goes to login).
    """
    if not getattr(settings, "LANDING_PAGE_ENABLED", True):
        return redirect("student_login")
    if request.user.is_authenticated:
        if getattr(request.user, "studentprofile", None):
            return redirect("student_dashboard")
        if getattr(request.user, "facultyprofile", None) and not request.user.is_staff:
            return redirect("teacher_dashboard")
        return redirect("admin_dashboard")

    if request.method == "POST":
        form = DemoRequestForm(request.POST)
        if form.is_valid():
            lead = form.save()
            logger.info("demo request from college=%s email=%s", lead.college_name, lead.email)
            return render(request, "landing.html", {
                "plans": _public_plans(),
                "form": DemoRequestForm(),
                "submitted": True,
                "college_name": lead.college_name,
            })
    else:
        form = DemoRequestForm()

    return render(request, "landing.html", {"plans": _public_plans(), "form": form})


def _public_plans():
    """Only what the college needs to see: name, price, limit, headline features."""
    from platform_admin.models import MODULES

    labels = dict(MODULES)
    plans = []
    for plan in Plan.objects.filter(is_active=True).order_by("price_monthly", "name")[:4]:
        plans.append({
            "name": plan.name,
            "price_monthly": plan.price_monthly,
            "student_limit": plan.student_limit,
            "features": [labels.get(code, code.replace("_", " ").title())
                         for code in (plan.features or [])],
        })
    return plans


def demo_request_count():
    return DemoRequest.objects.count()
