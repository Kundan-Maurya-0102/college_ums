"""Teacher panel: own students, attendance, marks, notices, materials, schedule."""

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import (
    AssignmentForm,
    ClassScheduleForm,
    InternalExamForm,
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
    faculty = request.user.facultyprofile
    subjects = _faculty_subjects(request.user)
    selected_semester = _int_or_none(request.GET.get("semester") or request.POST.get("semester"))
    selected_branch = (request.GET.get("branch") or request.POST.get("branch") or "").upper()
    selected_subject_id = _int_or_none(request.GET.get("subject") or request.POST.get("subject"))

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

    students = StudentProfile.objects.none()
    if selected_subject:
        students = _subject_class_students(selected_subject)
    elif selected_semester and selected_branch:
        students = StudentProfile.objects.filter(
            branch=selected_branch,
            semester=selected_semester,
        ).order_by("registration_number")

    form = InternalExamForm(request.POST or None)
    form.fields["subject"].queryset = filtered_subjects
    form.fields["student"].queryset = students
    if selected_subject:
        form.fields["subject"].initial = selected_subject

    if not selected_semester or not selected_branch:
        form.fields["student"].help_text = "Select semester and branch first."

    if not faculty.can_enter_marks:
        messages.error(request, "Marks entry permission is disabled for your account.")
        return redirect("teacher_dashboard")

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not subjects.filter(pk=obj.subject_id).exists():
            messages.error(request, "You can enter marks only for your assigned subjects.")
        elif obj.student.branch != obj.subject.branch or obj.student.semester != obj.subject.semester:
            messages.error(request, "This student is not in the selected subject class.")
        else:
            InternalExam.objects.update_or_create(
                student=obj.student,
                subject=obj.subject,
                exam_type=obj.exam_type,
                defaults={
                    "marks_obtained": obj.marks_obtained,
                    "max_marks": obj.max_marks,
                    "exam_date": obj.exam_date,
                },
            )
            messages.success(request, "Marks saved.")
            return redirect("teacher_marks")

    recent_marks = InternalExam.objects.filter(subject__in=subjects).select_related("student", "subject").order_by("-id")[:25]
    return render(request, "teacher/marks.html", {"show_dark_toggle": True,
        "form": form,
        "recent_marks": recent_marks,
        "subjects": subjects,
        "filtered_subjects": filtered_subjects,
        "available_semesters": available_semesters,
        "available_branches": available_branches,
        "selected_semester": selected_semester,
        "selected_branch": selected_branch,
        "selected_subject": selected_subject,
        "students": students,
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

