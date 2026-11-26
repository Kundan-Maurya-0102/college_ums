"""Teacher panel: own students, attendance, marks, notices, materials, schedule."""

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import (
    AssignmentForm,
    ClassScheduleForm,
    NoticeForm,
    StudyMaterialForm,
)
from ..models import (
    Assignment,
    Attendance,
    ClassSchedule,
    InternalExam,
    Notice,
    StudentProfile,
    StudyMaterial,
)
from .common import _date_or_today, _faculty_subjects, _int_or_none, _subject_class_students, teacher_required


@teacher_required
def teacher_students(request):
    subjects = _faculty_subjects(request.user)
    selected_subject_id = _int_or_none(request.GET.get("subject"))
    selected_subject = subjects.filter(pk=selected_subject_id).first() if selected_subject_id else subjects.first()
    students = (_subject_class_students(selected_subject) if selected_subject
                else StudentProfile.objects.none())

    query = (request.GET.get("q") or "").strip()[:60]
    if query:
        students = students.filter(Q(name__icontains=query) |
                                   Q(registration_number__icontains=query))

    # One grouped query instead of two per student (the row used to call
    # get_attendance_percentage(), which is 2 queries x every student).
    stats = {}
    if selected_subject:
        for row in (Attendance.objects.filter(subject=selected_subject,
                                             student__in=students)
                    .values("student_id")
                    .annotate(total=Count("id"),
                              present=Count("id", filter=Q(is_present=True)))):
            total = row["total"]
            stats[row["student_id"]] = (round(row["present"] / total * 100, 1) if total else 0)

    rows = [{"student": student, "percent": stats.get(student.id)}
            for student in students.order_by("registration_number")]

    return render(request, "teacher/students.html", {"show_dark_toggle": True,
        "subjects": subjects,
        "selected_subject": selected_subject,
        "rows": rows,
        "student_total": len(rows),
        "query": query,
    })


@teacher_required
def teacher_take_attendance(request):

    subjects = _faculty_subjects(request.user)
    selected_subject_id = _int_or_none(request.GET.get("subject") or request.POST.get("subject"))
    selected_date = _date_or_today(request.GET.get("date") or request.POST.get("date"))
    subject = subjects.filter(pk=selected_subject_id).first() if selected_subject_id else None
    students = _subject_class_students(subject) if subject else []
    existing_att = Attendance.objects.filter(subject=subject, date=selected_date) if subject else Attendance.objects.none()
    attendance_records = {att.student_id: att for att in existing_att}
    present_ids = [att.student_id for att in existing_att if att.is_present]

    if request.method == "POST" and subject:
        marked_by = request.user.facultyprofile.name
        for student in students:
            is_present = str(student.id) in request.POST.getlist("present_student_ids")
            att = attendance_records.get(student.id)
            if att:
                att.is_present = is_present
                att.marked_by = marked_by
                att.save()
            else:
                Attendance.objects.create(
                    student=student,
                    subject=subject,
                    date=selected_date,
                    is_present=is_present,
                    marked_by=marked_by,
                )
        messages.success(request, f"Attendance saved for {subject.subject_code}.")
        return redirect(f"/teacher/attendance/?subject={subject.id}&date={selected_date}")

    return render(request, "teacher/take_attendance.html", {"show_dark_toggle": True,
        "subjects": subjects,
        "selected_subject": subject,
        "selected_date": selected_date,
        "students": students,
        "present_ids": present_ids,
        "has_attendance": existing_att.exists(),
    })


@teacher_required
def teacher_marks(request):
    """Spreadsheet-style marks entry: one row per student, one POST for the whole class.

    Same URL and permission as before; the form now posts every row at once instead of
    one student at a time. `?export=csv` downloads the same grid, and a posted
    `csv_file` fills it (client-side preview, server-side authority).
    """
    import csv

    faculty = request.user.facultyprofile
    if not faculty.can_enter_marks:
        messages.error(request, "Marks entry permission is disabled for your account.")
        return redirect("teacher_dashboard")

    subjects = _faculty_subjects(request.user)
    params = request.POST if request.method == "POST" else request.GET
    selected_semester = _int_or_none(params.get("semester"))
    selected_branch = (params.get("branch") or "").upper()
    selected_subject_id = _int_or_none(params.get("subject"))

    available_semesters = sorted({subject.semester for subject in subjects})
    available_branches = sorted({subject.branch for subject in subjects})

    filtered_subjects = subjects
    if selected_semester:
        filtered_subjects = filtered_subjects.filter(semester=selected_semester)
    if selected_branch:
        filtered_subjects = filtered_subjects.filter(branch=selected_branch)

    selected_subject = None
    if selected_subject_id:
        selected_subject = filtered_subjects.filter(pk=selected_subject_id).first()
    if not selected_subject and filtered_subjects.count() == 1:
        selected_subject = filtered_subjects.first()

    exam_type = (params.get("exam_type") or "CA1").upper()
    exam_type = exam_type if exam_type in dict(InternalExam.EXAM_TYPES) else "CA1"
    try:
        max_marks = max(1, min(1000, int(params.get("max_marks") or 20)))
    except (TypeError, ValueError):
        max_marks = 20
    exam_date = _date_or_today(params.get("exam_date"))

    students = StudentProfile.objects.none()
    if selected_subject:
        students = _subject_class_students(selected_subject)
    elif selected_semester and selected_branch:
        students = StudentProfile.objects.filter(branch=selected_branch,
                                                 semester=selected_semester) \
            .order_by("registration_number")
    students = list(students)

    existing = {}
    if selected_subject and students:
        existing = {row["student_id"]: row["marks_obtained"]
                    for row in InternalExam.objects
                    .filter(subject=selected_subject, exam_type=exam_type,
                            student__in=students)
                    .values("student_id", "marks_obtained")}

    if request.method == "POST" and selected_subject:
        posted = {}
        errors = []
        for student in students:
            raw = (request.POST.get(f"marks_{student.pk}") or "").strip()
            if not raw:
                continue
            try:
                value = int(float(raw))
            except (TypeError, ValueError):
                errors.append(f"{student.registration_number}: not a number")
                continue
            if value < 0 or value > max_marks:
                errors.append(f"{student.registration_number}: {value} is outside 0–{max_marks}")
                continue
            posted[student.pk] = value

        if errors:
            for line in errors[:8]:
                messages.error(request, line)
        else:
            saved = 0
            for student in students:
                if student.pk not in posted:
                    continue
                InternalExam.objects.update_or_create(
                    student=student, subject=selected_subject, exam_type=exam_type,
                    defaults={"marks_obtained": posted[student.pk],
                              "max_marks": max_marks, "exam_date": exam_date},
                )
                saved += 1
            messages.success(
                request, f"Saved {saved} mark(s) for {selected_subject.subject_code} "
                         f"({exam_type}).")
            return redirect(f"{request.path}?semester={selected_semester or ''}"
                            f"&branch={selected_branch}&subject={selected_subject.pk}"
                            f"&exam_type={exam_type}&max_marks={max_marks}")

    rows = [{"student": student,
             "marks": existing.get(student.pk),
             "is_set": student.pk in existing} for student in students]

    if selected_subject and (request.GET.get("export") or "") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="marks-{selected_subject.subject_code}-{exam_type}.csv"')
        writer = csv.writer(response)
        writer.writerow(["registration_number", "name", "marks"])
        for row in rows:
            writer.writerow([row["student"].registration_number, row["student"].name,
                             "" if row["marks"] is None else row["marks"]])
        return response

    recent_marks = (InternalExam.objects.filter(subject__in=subjects)
                    .select_related("student", "subject").order_by("-id")[:25])
    return render(request, "teacher/marks.html", {
        "show_dark_toggle": True,
        "recent_marks": recent_marks,
        "subjects": subjects,
        "filtered_subjects": filtered_subjects,
        "available_semesters": available_semesters,
        "available_branches": available_branches,
        "selected_semester": selected_semester,
        "selected_branch": selected_branch,
        "selected_subject": selected_subject,
        "exam_type": exam_type,
        "exam_types": InternalExam.EXAM_TYPES,
        "max_marks": max_marks,
        "exam_date": exam_date,
        "rows": rows,
        "student_count": len(rows),
        "filled_count": sum(1 for row in rows if row["is_set"]),
        "branch_choices": StudentProfile.BRANCH_CHOICES,
    })


def _teacher_owned_form(request, form_class, model, template, title):
    faculty = request.user.facultyprofile
    subjects = _faculty_subjects(request.user)
    form = form_class(request.POST or None, request.FILES or None)
    form.fields["subject"].queryset = subjects
    if request.method == "POST":
        if form.is_valid():
            obj = form.save(commit=False)
            if not subjects.filter(pk=obj.subject_id).exists():
                messages.error(request, "Select one of your assigned subjects.")
            else:
                if hasattr(obj, "assigned_by"):
                    obj.assigned_by = faculty
                if hasattr(obj, "uploaded_by"):
                    obj.uploaded_by = faculty
                if hasattr(obj, "faculty"):
                    obj.faculty = faculty
                obj.save()
                messages.success(request, f"{title} saved.")
                return redirect(request.resolver_match.url_name)
        else:
            messages.error(request, "Please fix the errors below.")
    items = model.objects.filter(subject__in=subjects).select_related("subject").order_by("-id")[:50]
    return render(request, template, {
        "show_dark_toggle": True,
        "form": form,
        "items": items,
        "title": title,
        # optional per-deployment link, never a hardcoded drive id
        "DRIVE_FOLDER_URL": (getattr(settings, "MATERIAL_SHARED_FOLDER_URL", "") or "").strip(),
    })


@teacher_required
def teacher_assignments(request):
    return _teacher_owned_form(request, AssignmentForm, Assignment, "teacher/content_form.html", "Assignment")


@teacher_required
def teacher_materials(request):
    faculty = request.user.facultyprofile
    if not faculty.can_upload_materials:
        messages.error(request, "Material upload permission is disabled for your account.")
        return redirect("teacher_dashboard")
    return _teacher_owned_form(request, StudyMaterialForm, StudyMaterial, "teacher/content_form.html", "Note / PDF")


@teacher_required
def teacher_schedule(request):
    return _teacher_owned_form(request, ClassScheduleForm, ClassSchedule, "teacher/content_form.html", "Class Schedule")


@teacher_required
def teacher_notices(request):
    faculty = request.user.facultyprofile
    subjects = _faculty_subjects(request.user)
    if not faculty.can_send_notices:
        messages.error(request, "Notice permission is disabled for your account.")
        return redirect("teacher_dashboard")

    form = NoticeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        notice = form.save(commit=False)
        allowed_branches = {s.branch for s in subjects}
        allowed_semesters = {str(s.semester) for s in subjects}
        branches = {b.strip() for b in notice.target_branches.split(",") if b.strip()} or allowed_branches
        semesters = {s.strip() for s in notice.target_semesters.split(",") if s.strip()} or allowed_semesters
        if not branches.issubset(allowed_branches) or not semesters.issubset(allowed_semesters):
            messages.error(request, "Teacher notices can target only your assigned classes.")
        else:
            notice.target_branches = ",".join(sorted(branches))
            notice.target_semesters = ",".join(sorted(semesters))
            notice.created_by = faculty
            notice.save()
            messages.success(request, "Notice published.")
            return redirect("teacher_notices")
    branch_filters = Q(target_branches="")
    semester_filters = Q(target_semesters="")
    for subject in subjects:
        branch_filters |= Q(target_branches__icontains=subject.branch)
        semester_filters |= Q(target_semesters__icontains=str(subject.semester))
    notices = Notice.objects.filter(branch_filters, semester_filters).select_related("created_by").order_by("-created_at")[:50]
    return render(request, "teacher/notices.html", {"show_dark_toggle": True, "form": form, "notices": notices, "subjects": subjects})


@teacher_required
def teacher_notice_edit(request, pk):
    faculty = request.user.facultyprofile
    notice = get_object_or_404(Notice, pk=pk, created_by=faculty)
    subjects = _faculty_subjects(request.user)
    form = NoticeForm(request.POST or None, instance=notice)

    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        allowed_branches = {s.branch for s in subjects}
        allowed_semesters = {str(s.semester) for s in subjects}
        branches = {b.strip() for b in updated.target_branches.split(",") if b.strip()} or allowed_branches
        semesters = {s.strip() for s in updated.target_semesters.split(",") if s.strip()} or allowed_semesters
        if not branches.issubset(allowed_branches) or not semesters.issubset(allowed_semesters):
            messages.error(request, "Teacher notices can target only your assigned classes.")
        else:
            updated.target_branches = ",".join(sorted(branches))
            updated.target_semesters = ",".join(sorted(semesters))
            updated.created_by = faculty
            updated.save()
            messages.success(request, "Notice updated.")
            return redirect("teacher_notices")

    return render(request, "teacher/notice_form.html", {"show_dark_toggle": True,
        "form": form,
        "notice": notice,
        "action": "Edit",
    })


@teacher_required
def teacher_notice_delete(request, pk):
    faculty = request.user.facultyprofile
    notice = get_object_or_404(Notice, pk=pk, created_by=faculty)
    if request.method == "POST":
        title = notice.title
        notice.delete()
        messages.success(request, f"Notice '{title}' deleted.")
        return redirect("teacher_notices")
    return render(request, "teacher/notice_delete_confirm.html", {"show_dark_toggle": True, "notice": notice})

