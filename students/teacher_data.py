"""Teacher dashboard data: aggregates only, and only for the teacher's own subjects.

Everything here answers one question — "what needs me today?" — so the dashboard never
runs a query per student or per subject.
"""

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from .models import (
    Assignment,
    Attendance,
    ClassSchedule,
    Doubt,
    Event,
    ExamSchedule,
    LeaveApplication,
    Notice,
    StudentProfile,
    StudyMaterial,
)

RISK_LIMIT = 5

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def my_subjects(faculty):
    return faculty.subjects.filter(is_active=True).order_by("branch", "semester", "subject_code")


def _class_students_q(subjects):
    """Every student in the classes the teacher teaches (one query)."""
    condition = Q()
    for subject in subjects:
        condition |= Q(branch=subject.branch, semester=subject.semester)
    if not condition:
        return StudentProfile.objects.none()
    return StudentProfile.objects.filter(condition)


def today_classes(faculty):
    """Today's timetable slots with the room and the subject, in one query."""
    today = timezone.localdate().weekday()
    slots = (ClassSchedule.objects
             .filter(faculty=faculty, is_active=True, weekday=today)
             .select_related("subject")
             .order_by("start_time"))
    taken = set(
        Attendance.objects
        .filter(subject__in=[slot.subject_id for slot in slots], date=timezone.localdate())
        .values_list("subject_id", flat=True)
    )
    return [{"slot": slot, "attendance_taken": slot.subject_id in taken} for slot in slots]


def subject_rows(faculty):
    """Per subject: class size, how many classes held, average attendance (2 queries)."""
    subjects = list(my_subjects(faculty))
    if not subjects:
        return []

    counts = (_class_students_q(subjects)
              .values("branch", "semester")
              .annotate(total=Count("id")))
    size = {(row["branch"], row["semester"]): row["total"] for row in counts}

    stats = (Attendance.objects
             .filter(subject__in=subjects)
             .values("subject_id")
             .annotate(held=Count("id"),
                       present=Count("id", filter=Q(is_present=True)),
                       days=Count("date", distinct=True)))
    by_subject = {row["subject_id"]: row for row in stats}

    rows = []
    for subject in subjects:
        row = by_subject.get(subject.id, {})
        held = row.get("held", 0)
        present = row.get("present", 0)
        percent = round(present / held * 100, 1) if held else None
        rows.append({
            "subject": subject,
            "students": size.get((subject.branch, subject.semester), 0),
            "classes": row.get("days", 0),
            "percent": percent,
            "state": ("none" if percent is None else
                      "ok" if percent >= 75 else "watch" if percent >= 60 else "low"),
        })
    return rows


def at_risk(faculty, limit=RISK_LIMIT):
    """The students closest to the 75% rule, worst first (3 queries)."""
    subjects = list(my_subjects(faculty))
    if not subjects:
        return []

    rows = (Attendance.objects
            .filter(subject__in=subjects)
            .values("student_id", "subject_id")
            .annotate(total=Count("id"), present=Count("id", filter=Q(is_present=True))))
    scored = []
    for row in rows:
        if not row["total"]:
            continue
        percent = round(row["present"] / row["total"] * 100, 1)
        if percent < 75:
            scored.append((row["student_id"], row["subject_id"], percent, row["total"]))
    scored.sort(key=lambda item: (item[2], -item[3]))

    students = StudentProfile.objects.in_bulk({item[0] for item in scored[:limit]})
    by_id = {subject.id: subject for subject in subjects}
    out = []
    for student_id, subject_id, percent, total in scored[:limit]:
        student = students.get(student_id)
        if student is None or subject_id not in by_id:
            continue
        out.append({
            "student": student,
            "subject": by_id[subject_id],
            "percent": percent,
            "held": total,
            "state": "low" if percent < 60 else "watch",
        })
    return out


def pending_work(faculty, subject_rows_data, classes):
    """Counts for the four things a teacher usually owes the college."""
    subjects = [row["subject"] for row in subject_rows_data]
    today = timezone.localdate()

    attendance_pending = sum(1 for item in classes if not item["attendance_taken"])
    marks_pending = 0
    if subjects:
        marked = set(Attendance.objects.filter(subject__in=subjects, date=today)
                     .values_list("subject_id", flat=True))
        marks_pending = len([s for s in subjects if s.id not in marked])

    submissions = (Assignment.objects.filter(subject__in=subjects, is_active=True)
                   .filter(due_date__lt=today).count()) if subjects else 0
    leave_waiting = LeaveApplication.objects.filter(status="PENDING").count()

    return [
        {"key": "attendance", "label": "Attendance not taken today",
         "count": attendance_pending, "url": reverse("teacher_take_attendance")},
        {"key": "marks", "label": "Subjects without attendance marks today",
         "count": marks_pending, "url": reverse("teacher_marks")},
        {"key": "assignments", "label": "Assignments past their due date",
         "count": submissions, "url": reverse("teacher_assignments")},
        {"key": "leave", "label": "Leave requests waiting with the office",
         "count": leave_waiting, "url": None},
    ]


def recent_content(faculty):
    """Latest notices and the material this teacher uploaded (2 queries)."""
    notices = (Notice.objects.filter(is_active=True)
               .filter(Q(created_by=faculty) | Q(target_branches="") )
               .select_related("created_by")
               .order_by("-created_at")[:4])
    materials = (StudyMaterial.objects.filter(uploaded_by=faculty, is_active=True)
                 .select_related("subject").order_by("-created_at")[:4])
    return list(notices), list(materials)


def upcoming(faculty):
    """Next exams for the teacher's classes and the next events (2 queries)."""
    subjects = list(my_subjects(faculty))
    today = timezone.localdate()
    exams = (ExamSchedule.objects
             .filter(subject__in=subjects, exam_date__gte=today)
             .select_related("subject").order_by("exam_date")[:4]) if subjects else ExamSchedule.objects.none()
    events = (Event.objects.filter(is_active=True, event_date__gte=today)
              .order_by("event_date")[:4])
    return list(exams), list(events)


def open_doubts(faculty, limit=4):
    """Unanswered doubts from the teacher's own classes (1 query)."""
    subjects = list(my_subjects(faculty))
    if not subjects:
        return []
    condition = Q()
    for subject in subjects:
        condition |= Q(student__branch=subject.branch, student__semester=subject.semester)
    doubts = (Doubt.objects.filter(is_resolved=False).filter(condition)
              .select_related("student").order_by("created_at")[:limit])
    return [{"doubt": doubt, "replies": doubt.replies.count()} for doubt in doubts]


def build(faculty):
    """Everything the teacher dashboard needs, assembled once."""
    classes = today_classes(faculty)
    rows = subject_rows(faculty)
    notices, materials = recent_content(faculty)
    exams, events = upcoming(faculty)

    overall_held = sum(row["classes"] for row in rows)
    return {
        "classes_today": classes,
        "subject_rows": rows,
        "at_risk": at_risk(faculty),
        "pending": pending_work(faculty, rows, classes),
        "notices": notices,
        "materials": materials,
        "exams": exams,
        "events": events,
        "doubts": open_doubts(faculty),
        "student_count": (_class_students_q([row["subject"] for row in rows]).count()
                          if rows else 0),
        "subject_count": len(rows),
        "classes_held": overall_held,
        "weekday": WEEKDAY_NAMES[timezone.localdate().weekday()],
        "today": timezone.localdate(),
    }
