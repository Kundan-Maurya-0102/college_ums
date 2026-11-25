"""Everything the student dashboard shows, in a fixed number of queries.

One screen means one page: notices, messages, courses with attendance rings, today's
classes, fees, pending assignments, events, next exams and a result summary. Built here
(not in the view) so the query budget can be tested directly.

Rules:
  * only `profile`'s own rows — never a filter that another student could satisfy;
  * aggregates, not per-row queries (`Count`/`Sum` with `filter=`, one query per card);
  * every card degrades to an empty list, never an exception (a new college has no data).
"""
from datetime import timedelta

from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import (
    Assignment,
    Attendance,
    ClassSchedule,
    Event,
    ExamSchedule,
    FeePayment,
    FeeStructure,
    Notice,
    SemesterResult,
    StudentProfile,
    StudyMaterial,
    Subject,
)

ATTENDANCE_OK = 75.0      # green at or above
ATTENDANCE_WATCH = 60.0   # amber between WATCH and OK, red below

#: Default quick links (label, url name, icon id from templates/partials/icons.html).
DEFAULT_QUICK_LINKS = [
    {"label": "Fee Dashboard", "url_name": "student_fees", "icon": "i-rupee", "badge": ""},
    {"label": "Date Sheet", "url_name": "student_exam_schedule", "icon": "i-calendar", "badge": "exam"},
    {"label": "Hall ticket", "url_name": "exam_documents", "icon": "i-download", "badge": ""},
    {"label": "Certificate Request", "url_name": "student_certificates", "icon": "i-shield", "badge": ""},
    {"label": "Leave Apply", "url_name": "student_leave_apply", "icon": "i-clipboard", "badge": ""},
    {"label": "Academic Calendar", "url_name": "student_events", "icon": "i-calendar", "badge": ""},
    {"label": "Help", "url_name": "help_center", "icon": "i-message", "badge": ""},
]


def _subjects(profile, query=''):
    if not (profile.branch and profile.semester):
        return Subject.objects.none()
    subjects = Subject.objects.filter(
        branch=profile.branch, semester=profile.semester, is_active=True)
    if query:
        subjects = subjects.filter(
            Q(subject_name__icontains=query) | Q(subject_code__icontains=query))
    return subjects


def _ring_state(percent):
    if percent is None:
        return "none"
    if percent >= ATTENDANCE_OK:
        return "ok"
    if percent >= ATTENDANCE_WATCH:
        return "watch"
    return "low"


def courses(profile, query=''):
    """Subjects + attendance % + today's class, in two queries."""
    subjects = list(_subjects(profile, query).order_by("subject_code"))
    if not subjects:
        return []

    subject_ids = [s.pk for s in subjects]

    # One grouped query for all subjects (no per-subject count()).
    stats = {
        row["subject_id"]: row
        for row in Attendance.objects.filter(student=profile, subject_id__in=subject_ids)
        .values("subject_id")
        .annotate(total=Count("id"), present=Count("id", filter=Q(is_present=True)))
    }

    today = timezone.localdate()
    today_schedule = {
        row["subject_id"]: row
        for row in ClassSchedule.objects.filter(
            subject_id__in=subject_ids, weekday=today.weekday(), is_active=True)
        .values("subject_id", "start_time", "end_time", "room")
    }

    materials = {
        row["subject_id"]: row["count"]
        for row in StudyMaterial.objects.filter(subject_id__in=subject_ids, is_active=True)
        .values("subject_id").annotate(count=Count("id"))
    }

    rows = []
    for subject in subjects:
        row = stats.get(subject.pk)
        total = row["total"] if row else 0
        present = row["present"] if row else 0
        percent = round(present / total * 100, 1) if total else None
        slot = today_schedule.get(subject.pk)
        rows.append({
            "subject": subject,
            "attended": present,
            "held": total,
            "percent": percent,
            "ring": _ring_state(percent),
            "today": slot,
            "material_count": materials.get(subject.pk, 0),
        })
    return rows


def attendance_summary(profile, course_rows):
    """Overall % from the same numbers the rings use (no extra query)."""
    held = sum(r["held"] for r in course_rows)
    attended = sum(r["attended"] for r in course_rows)
    percent = round(attended / held * 100, 1) if held else None
    return {"held": held, "attended": attended, "percent": percent,
            "ring": _ring_state(percent)}


def notices_and_messages(profile, course_rows, limit=5, query=''):
    """Announcements for everyone, plus messages aimed at this student.

    A notice is a "message" when it targets a branch/semester (i.e. it was written for
    a class, not the whole college). Read state is `dashboard_seen_at` on *this* row.
    """
    by_subject = {r["subject"].pk: r["subject"] for r in course_rows}
    queryset = (Notice.objects.filter(is_active=True)
                .select_related("created_by")
                .order_by("-created_at"))

    announcements, messages = [], []
    # Bounded scan: recent notices only, so a big college does not load the table.
    needle = (query or '').lower()
    for notice in queryset[:60]:
        if not notice.is_for_student(profile):
            continue
        if needle and needle not in (notice.title or '').lower() \
                and needle not in (notice.content or '').lower():
            continue
        entry = {"notice": notice, "unread": _is_unread(notice, profile)}
        targeted = bool(notice.target_branches or notice.target_semesters)
        if targeted and len(messages) < limit:
            messages.append(entry)
        elif not targeted and len(announcements) < limit:
            announcements.append(entry)
        if len(announcements) >= limit and len(messages) >= limit:
            break
    unread_total = sum(1 for e in announcements + messages if e["unread"])
    return {"announcements": announcements, "messages": messages,
            "unread": unread_total, "subjects": by_subject}


def _is_unread(notice, profile):
    seen = profile.dashboard_seen_at
    return bool(seen is None or notice.created_at > seen)


def fees(profile, gateway_configured):
    """Due amount, status and the latest receipts — two queries."""
    structures = list(FeeStructure.objects.filter(
        branch=profile.branch, is_active=True,
        semester=profile.semester) if profile.branch and profile.semester else [])

    payable = FeeStructure.objects.none()
    if structures:
        payable = FeeStructure.objects.filter(pk__in=[s.pk for s in structures])

    totals = payable.aggregate(
        amount=Coalesce(Sum("amount"), Value(0, output_field=DecimalField())))
    paid = (FeePayment.objects.filter(student=profile)
            .aggregate(total=Coalesce(Sum("amount_paid"), Value(0, output_field=DecimalField()))))
    due_amount = (totals["amount"] or 0) - (paid["total"] or 0)
    if due_amount < 0:
        due_amount = 0

    due_dates = [s.due_date for s in structures if s.due_date]
    next_due = min(due_dates) if due_dates else None
    today = timezone.localdate()
    if due_amount <= 0:
        status = "paid"
    elif next_due and next_due < today:
        status = "overdue"
    else:
        status = "due"

    receipts = list(FeePayment.objects.filter(student=profile)
                    .select_related("fee_structure").order_by("-payment_date")[:3])
    return {
        "total": totals["amount"] or 0,
        "paid": paid["total"] or 0,
        "due": due_amount,
        "status": status,
        "due_date": next_due,
        "receipts": receipts,
        "pay_online": bool(gateway_configured and due_amount > 0),
    }


def assignments(profile, course_rows, limit=5):
    """Assignments for this student's subjects, pending first (one query)."""
    subject_ids = [r["subject"].pk for r in course_rows]
    if not subject_ids:
        return []
    today = timezone.localdate()
    rows = (Assignment.objects.filter(subject_id__in=subject_ids, is_active=True)
            .select_related("subject", "assigned_by")
            .order_by(F("due_date").asc(nulls_last=True), "-created_at")[:limit])
    out = []
    for row in rows:
        overdue = bool(row.due_date and row.due_date < today)
        out.append({"assignment": row, "overdue": overdue})
    return out


def upcoming_events(limit=4):
    today = timezone.localdate()
    return list(Event.objects.filter(is_active=True, event_date__gte=today)
                .order_by("event_date")[:limit])


def upcoming_exams(profile, limit=3, course_rows=None):
    """Next exams for this student's branch/semester (one query)."""
    if not (profile.branch and profile.semester):
        return []
    today = timezone.localdate()
    return list(ExamSchedule.objects.filter(
        branch=profile.branch, semester=profile.semester, is_active=True,
        exam_date__gte=today).select_related("subject").order_by("exam_date", "start_time")[:limit])


def has_new_exam_schedule(profile, within_days=14):
    """Badge for the Date Sheet quick link: an exam schedule added recently."""
    if not (profile.branch and profile.semester):
        return False
    since = timezone.now() - timedelta(days=within_days)
    return ExamSchedule.objects.filter(
        branch=profile.branch, semester=profile.semester, is_active=True,
        created_at__gte=since).exists()


def latest_result(profile):
    """Latest published semester result (one query, then a tiny aggregate)."""
    rows = (SemesterResult.objects.filter(student=profile)
            .select_related("subject").order_by("-semester", "subject__subject_code"))
    if not rows:
        return None
    semester = rows[0].semester
    items = [r for r in rows if r.semester == semester]
    total = sum(r.total_marks for r in items)
    passed = sum(1 for r in items if r.is_pass)
    return {
        "semester": semester,
        "subjects": len(items),
        "passed": passed,
        "failed": len(items) - passed,
        "total_marks": total,
        "average": round(total / len(items), 1) if items else 0,
        "is_pass": passed == len(items),
        "rows": items[:8],
    }


def banner(profile, fee_card):
    """One short banner: old password first, then money, then attendance."""
    if not profile.is_password_changed:
        return {"kind": "danger", "title": "Change your password",
                "text": "You are still on the password the office gave you.",
                "url_name": "change_password", "label": "Change now"}
    if fee_card["status"] == "overdue":
        return {"kind": "danger", "title": "Fee overdue",
                "text": f"₹{fee_card['due']:,.0f} is pending past the due date.",
                "url_name": "student_fees", "label": "See fees"}
    if fee_card["due"] > 0 and fee_card["due_date"]:
        return {"kind": "warning", "title": "Fee due",
                "text": f"₹{fee_card['due']:,.0f} due by {fee_card['due_date']:%d %b %Y}.",
                "url_name": "student_fees", "label": "See fees"}
    return None


def build(profile, gateway_configured=False, cards=None, query=''):
    """Assemble the whole dashboard context. `query` is the navbar search."""
    query = (query or '').strip()
    course_rows = courses(profile, query)
    attendance = attendance_summary(profile, course_rows)
    notice_block = notices_and_messages(profile, course_rows, query=query)
    fee_card = fees(profile, gateway_configured)
    result = latest_result(profile)

    return {
        "course_rows": course_rows,
        "attendance": attendance,
        "announcements": notice_block["announcements"],
        "messages": notice_block["messages"],
        "unread_count": notice_block["unread"],
        "fee_card": fee_card,
        "pending_assignments": assignments(profile, course_rows),
        "events": upcoming_events(),
        "exams": upcoming_exams(profile),
        "new_exam_schedule": has_new_exam_schedule(profile),
        "latest_result": result,
        "cgpa": cgpa(profile),
        "banner": banner(profile, fee_card),
        "cards": cards,
        "query": query,
        "is_searching": bool(query),
        "has_any_data": bool(course_rows or notice_block["announcements"]
                             or notice_block["messages"] or result
                             or fee_card["total"] or fee_card["paid"]),
    }


def cgpa(profile):
    """Credit-weighted CGPA across every published semester (None if none)."""
    from .exams import gpa, grade_point

    rows = [{"credits": row.subject.credits or 0, "point": grade_point(row.grade),
             "is_pass": row.is_pass}
            for row in SemesterResult.objects.filter(student=profile).select_related("subject")]
    return gpa(rows)


def mark_seen(profile):
    """Remember that this student has now seen the dashboard (unread dots only)."""
    StudentProfile.objects.filter(pk=profile.pk).update(dashboard_seen_at=timezone.now())
