"""Admin dashboard data: aggregates for the stat cards, charts and the "pay attention" panel.

Every chart series is one GROUP BY query — the dashboard must not get slower as the
college grows.
"""
import datetime
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone

from .models import (
    Attendance,
    AuditLog,
    BackupRecord,
    ErrorEvent,
    FacultyProfile,
    FeePayment,
    FeeStructure,
    LeaveApplication,
    SemesterResult,
    StudentProfile,
    Subject,
)


def _month_start(day):
    return day.replace(day=1)


def _money_and_attendance():
    """The aggregates both the cards and the attention panel need, fetched once."""
    today = timezone.localdate()
    attendance_today = Attendance.objects.filter(date=today).aggregate(
        total=Count("id"), present=Count("id", filter=Q(is_present=True)))
    billed = (FeeStructure.objects.filter(is_active=True)
              .aggregate(amount=Sum("amount"))["amount"] or Decimal("0"))
    collected_month = (FeePayment.objects.filter(payment_date__gte=_month_start(today))
                       .aggregate(amount=Sum("amount_paid"))["amount"] or Decimal("0"))
    per_student = {row["student_id"]: row["amount"] or Decimal("0")
                   for row in FeePayment.objects.values("student_id")
                   .annotate(amount=Sum("amount_paid"))}
    paid_total = sum(per_student.values(), Decimal("0"))
    return {
        "attendance_total": attendance_today["total"] or 0,
        "attendance_present": attendance_today["present"] or 0,
        "billed": billed,
        "paid_total": paid_total,
        "collected_month": collected_month,
        "paid_by_student": per_student,
        "pending_leave": LeaveApplication.objects.filter(status="PENDING").count(),
    }


def stat_cards(shared=None):
    """Six numbers a principal actually asks for, each with its own drill-down URL."""
    shared = shared or _money_and_attendance()
    total = shared["attendance_total"]
    present = shared["attendance_present"]
    today_percent = round(present / total * 100, 1) if total else None
    pf = 0
    try:
        pf = int(shared["paid_total"] or 0)
    except Exception:  # pragma: no cover - defensive
        pf = 0
    collected = shared["collected_month"]
    pending_fees = max(shared["billed"] - shared["paid_total"], Decimal("0"))
    del pf

    return [
        {"key": "students", "label": "Total students",
         "value": shared.get("students_total", 0),
         "url": reverse("student_list")},
        {"key": "teachers", "label": "Teachers",
         "value": FacultyProfile.objects.filter(is_active=True).count(),
         "url": reverse("teacher_list")},
        {"key": "attendance", "label": "Attendance today",
         "value": "—" if today_percent is None else f"{today_percent}%",
         "hint": f"{present}/{total} marked", "url": reverse("reports_view")},
        {"key": "fees_month", "label": "Fees collected (this month)",
         "value": f"₹{collected:,.0f}", "url": reverse("fee_payments")},
        {"key": "fees_pending", "label": "Pending fees",
         "value": f"₹{pending_fees:,.0f}", "url": reverse("student_list")},
        {"key": "leave", "label": "Leave waiting",
         "value": shared["pending_leave"],
         "url": reverse("leave_applications")},
    ]


def charts():
    """Four series for Chart.js, each a single GROUP BY."""
    branch_names = dict(StudentProfile.BRANCH_CHOICES)
    branches = [{"label": branch_names.get(row["branch"], row["branch"]), "value": row["count"]}
                for row in StudentProfile.objects.values("branch")
                .annotate(count=Count("id")).order_by("branch")]

    today = timezone.localdate()
    months = []
    for back in range(5, -1, -1):
        first = _month_start(today.replace(day=1) - datetime.timedelta(days=back * 30))
        months.append(first)
    # One row per month, whatever the database: group in Python over one query.
    fee_rows = (FeePayment.objects.filter(payment_date__gte=months[0])
                .values("payment_date", "amount_paid"))
    buckets = {}
    for row in fee_rows:
        key = row["payment_date"].strftime("%b %Y")
        buckets[key] = buckets.get(key, 0) + float(row["amount_paid"] or 0)
    order = [month.strftime("%b %Y") for month in months]
    fees = [{"label": key, "value": buckets.get(key, 0)} for key in order]

    trend_rows = (Attendance.objects.filter(date__gte=today - datetime.timedelta(days=29))
                  .values("date")
                  .annotate(total=Count("id"), present=Count("id", filter=Q(is_present=True)))
                  .order_by("date"))
    trend = [{"label": row["date"].strftime("%d %b"),
              "value": round(row["present"] / row["total"] * 100, 1) if row["total"] else 0}
             for row in trend_rows]

    results = SemesterResult.objects.aggregate(
        total=Count("id"), passed=Count("id", filter=Q(is_pass=True)))
    pass_rate = round(results["passed"] / results["total"] * 100, 1) if results["total"] else None

    return {"branches": branches, "fees": fees, "trend": trend, "pass_rate": pass_rate}


def attention(shared=None):
    """The "watch this" panel: worst first, every row links somewhere useful."""
    shared = shared or _money_and_attendance()
    stats = (Attendance.objects.values("student_id")
             .annotate(total=Count("id"), present=Count("id", filter=Q(is_present=True))))
    low = []
    for row in stats:
        if not row["total"]:
            continue
        percent = round(row["present"] / row["total"] * 100, 1)
        if percent < 75:
            low.append((row["student_id"], percent))
    low.sort(key=lambda item: item[1])
    low = low[:5]

    unpaid = sorted(((sid, shared["billed"] - amount)
                     for sid, amount in shared["paid_by_student"].items()),
                    key=lambda item: item[1], reverse=True)
    unpaid = [item for item in unpaid if item[1] > 0][:5]

    # one lookup for both lists instead of two
    people = StudentProfile.objects.in_bulk({sid for sid, _ in low} | {sid for sid, _ in unpaid})
    low_rows = [{"student": people[sid], "percent": percent}
                for sid, percent in low if sid in people]
    defaulter_rows = [{"student": people[sid], "due": due}
                      for sid, due in unpaid if sid in people]

    pending_leave = shared["pending_leave"]
    errors = ErrorEvent.objects.filter(is_resolved=False).aggregate(c=Count("id"))["c"] or 0
    last_backup = BackupRecord.objects.order_by("-created_at").first()

    return {
        "low_attendance": low_rows,
        "defaulters": defaulter_rows,
        "pending_leave": pending_leave,
        "unresolved_errors": errors,
        "last_backup": last_backup,
        "no_backup": last_backup is None,
    }


def activity(limit=8):
    rows = (AuditLog.objects.select_related("user").order_by("-created_at")[:limit])
    return [{"log": row,
             "who": (row.user.get_full_name() or row.user.username) if row.user else "system"}
            for row in rows]


def quick_actions():
    return [
        {"label": "Add student", "url": reverse("student_create"), "icon": "i-users"},
        {"label": "Upload CSV", "url": reverse("csv_upload"), "icon": "i-upload"},
        {"label": "Post notice", "url": reverse("notice_create"), "icon": "i-bell"},
        {"label": "Add fee payment", "url": reverse("fee_payment_create"), "icon": "i-rupee"},
        {"label": "Reports", "url": reverse("reports_view"), "icon": "i-chart"},
        {"label": "Exam documents", "url": reverse("admin_exam_documents"), "icon": "i-clipboard"},
    ]


def build():
    shared = _money_and_attendance()
    chart_data = charts()
    # the branch series already contains the total, so no extra COUNT query
    shared["students_total"] = sum(row["value"] for row in chart_data["branches"])
    return {
        "stat_cards": stat_cards(shared),
        "charts": chart_data,
        "attention": attention(shared),
        "activity": activity(),
        "quick_actions": quick_actions(),
        "subject_count": Subject.objects.filter(is_active=True).count(),
    }
