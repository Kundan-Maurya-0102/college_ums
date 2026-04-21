import csv
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .ai_helper import get_ai_response
from .upload_router import process_any_csv_upload
from .password_links import build_set_password_link
from .forms import (AssignmentForm, BannerImageForm, CSVUploadForm, ClassScheduleForm,
                    DoubtForm, DoubtReplyForm, FacultyProfileForm, InternalExamForm, 
                    NoticeForm, StudentProfileForm, StudyMaterialForm, SubjectForm)
from .models import (Assignment, Attendance, BannerImage, CSVUpload, ClassSchedule,
                     Doubt, DoubtReply, FacultyProfile, InternalExam, Notice, 
                     SemesterResult, StudentProfile, StudyMaterial, Subject, WebsiteVisit)


def is_admin(user):
    if not (user.is_authenticated and user.is_staff):
        return False
    if user.is_superuser:
        return True
    return not hasattr(user, "facultyprofile")


def is_teacher(user):
    return (
        user.is_authenticated
        and user.is_staff
        and hasattr(user, "facultyprofile")
        and user.facultyprofile.is_active
    )

def admin_required(view_func):
    decorated = login_required(user_passes_test(is_admin, login_url='/login/')(view_func))
    return decorated


def teacher_required(view_func):
    decorated = login_required(user_passes_test(is_teacher, login_url='/login/')(view_func))
    return decorated


def _faculty_subjects(user):
    return user.facultyprofile.subjects.filter(is_active=True).order_by("branch", "semester", "subject_code")


def _subject_class_students(subject):
    return StudentProfile.objects.filter(branch=subject.branch, semester=subject.semester).order_by("registration_number")

def plane(request):
    return render(request, 'plane.html')

    

# ─────────────────────────── DASHBOARD ───────────────────────────

@admin_required
def admin_dashboard(request):
    total_students = StudentProfile.objects.count()
    branch_stats = {}
    for branch_code, branch_name in StudentProfile.BRANCH_CHOICES:
        count = StudentProfile.objects.filter(branch=branch_code).count()
        if count > 0:
            branch_stats[branch_name] = count

    recent_uploads = CSVUpload.objects.order_by('-upload_date')[:5]
    recent_students = StudentProfile.objects.order_by('-created_at')[:8]
    total_notices = Notice.objects.filter(is_active=True).count()
    total_subjects = Subject.objects.filter(is_active=True).count()
    total_teachers = FacultyProfile.objects.filter(is_active=True).count()
    total_attendance = Attendance.objects.count()
    present_attendance = Attendance.objects.filter(is_present=True).count()
    attendance_average = round((present_attendance / total_attendance) * 100, 1) if total_attendance else 0
    total_visits = WebsiteVisit.objects.count()
    today_visits = WebsiteVisit.objects.filter(visited_at__date=__import__("datetime").date.today()).count()
    total_visit_minutes = round(sum(v.duration_seconds for v in WebsiteVisit.objects.all()) / 60, 1)

    low_attendance_students = []
    for student in StudentProfile.objects.all().order_by("branch", "semester", "name")[:200]:
        pct = student.get_attendance_percentage()
        if pct and pct < 75:
            low_attendance_students.append({"student": student, "percentage": pct})
        if len(low_attendance_students) >= 8:
            break

    context = {
        'total_students': total_students,
        'branch_stats': branch_stats,
        'recent_uploads': recent_uploads,
        'recent_students': recent_students,
        'total_notices': total_notices,
        'total_subjects': total_subjects,
        'total_teachers': total_teachers,
        'attendance_average': attendance_average,
        'total_visits': total_visits,
        'today_visits': today_visits,
        'total_visit_minutes': total_visit_minutes,
        'low_attendance_students': low_attendance_students,
    }
    return render(request, 'admin_dashboard/index.html', context)


@admin_required
def teacher_list(request):
    teachers = FacultyProfile.objects.select_related("user").prefetch_related("subjects").order_by("name")
    return render(request, "admin_dashboard/teachers.html", {"teachers": teachers})


@admin_required
def teacher_create(request):
    form = FacultyProfileForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            teacher = form.save()
            messages.success(request, f"Teacher {teacher.name} added.")
            return redirect("teacher_list")
        messages.error(request, "Please fix the errors below.")
    return render(request, "admin_dashboard/teacher_form.html", {"form": form, "action": "Add"})


@admin_required
def teacher_edit(request, pk):
    teacher = get_object_or_404(FacultyProfile, pk=pk)
    form = FacultyProfileForm(request.POST or None, instance=teacher)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, f"Teacher {teacher.name} updated.")
            return redirect("teacher_list")
        messages.error(request, "Please fix the errors below.")
    return render(request, "admin_dashboard/teacher_form.html", {"form": form, "teacher": teacher, "action": "Edit"})


@admin_required
def teacher_delete(request, pk):
    teacher = get_object_or_404(FacultyProfile, pk=pk)
    if request.method == "POST":
        name = teacher.name
        user = teacher.user
        user.delete()
        messages.success(request, f"Teacher '{name}' deleted.")
        return redirect("teacher_list")
    related_counts = {
        "subjects": teacher.subjects.count(),
        "assignments": Assignment.objects.filter(assigned_by=teacher).count(),
        "materials": StudyMaterial.objects.filter(uploaded_by=teacher).count(),
        "schedules": ClassSchedule.objects.filter(faculty=teacher).count(),
    }
    return render(request, "admin_dashboard/teacher_delete_confirm.html", {
        "teacher": teacher,
        "related_counts": related_counts,
    })


@teacher_required
def teacher_dashboard(request):
    faculty = request.user.facultyprofile
    subjects = _faculty_subjects(request.user)
    attendance_qs = Attendance.objects.filter(subject__in=subjects)
    classes_taken = attendance_qs.values("subject_id", "date").distinct().count()
    total_marks = InternalExam.objects.filter(subject__in=subjects).count()

    total_records = attendance_qs.count()
    present_records = attendance_qs.filter(is_present=True).count()
    avg_attendance = round((present_records / total_records) * 100, 1) if total_records else 0

    student_ids = set()
    for subject in subjects:
        student_ids.update(_subject_class_students(subject).values_list("id", flat=True))

    low_attendance = []
    for student in StudentProfile.objects.filter(id__in=student_ids).order_by("name"):
        for subject in subjects.filter(branch=student.branch, semester=student.semester):
            pct = student.get_attendance_percentage(subject)
            if pct and pct < 75:
                low_attendance.append({"student": student, "subject": subject, "percentage": pct})
            if len(low_attendance) >= 8:
                break
        if len(low_attendance) >= 8:
            break

    high_marks = InternalExam.objects.filter(subject__in=subjects).select_related("student", "subject").order_by("-marks_obtained")[:8]
    schedules = ClassSchedule.objects.filter(faculty=faculty, is_active=True).select_related("subject")[:8]

    return render(request, "teacher/dashboard.html", {
        "faculty": faculty,
        "subjects": subjects,
        "classes_taken": classes_taken,
        "student_count": len(student_ids),
        "avg_attendance": avg_attendance,
        "total_marks": total_marks,
        "low_attendance": low_attendance,
        "high_marks": high_marks,
        "schedules": schedules,
    })


@teacher_required
def teacher_students(request):
    subjects = _faculty_subjects(request.user)
    selected_subject_id = request.GET.get("subject")
    selected_subject = subjects.filter(pk=selected_subject_id).first() if selected_subject_id else subjects.first()
    students = _subject_class_students(selected_subject) if selected_subject else StudentProfile.objects.none()
    return render(request, "teacher/students.html", {
        "subjects": subjects,
        "selected_subject": selected_subject,
        "students": students,
    })


@teacher_required
def teacher_take_attendance(request):
    import datetime

    subjects = _faculty_subjects(request.user)
    selected_subject_id = request.GET.get("subject") or request.POST.get("subject")
    selected_date = request.GET.get("date") or request.POST.get("date") or datetime.date.today().strftime("%Y-%m-%d")
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

    return render(request, "teacher/take_attendance.html", {
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
    selected_semester = request.GET.get("semester") or request.POST.get("semester") or ""
    selected_branch = request.GET.get("branch") or request.POST.get("branch") or ""
    selected_subject_id = request.GET.get("subject") or request.POST.get("subject") or ""

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
    return render(request, "teacher/marks.html", {
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
    return render(request, template, {"form": form, "items": items, "title": title})


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
    return render(request, "teacher/notices.html", {"form": form, "notices": notices, "subjects": subjects})


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

    return render(request, "teacher/notice_form.html", {
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
    return render(request, "teacher/notice_delete_confirm.html", {"notice": notice})


# ─────────────────────────── CSV UPLOAD ───────────────────────────

@admin_required
def csv_upload(request):
    result = None
    form = CSVUploadForm()

    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.uploaded_by = request.user.get_full_name() or request.user.username
            upload.save()

            result = process_any_csv_upload(upload)
            # Save generic counters for any dataset type
            upload.is_processed = True
            upload.records_created = int(result.get("created", 0) or 0)
            upload.records_updated = int(result.get("updated", 0) or 0)
            upload.errors = "\n".join(result.get("errors", []) or [])
            upload.save()

            messages.success(
                request,
                f"✅ CSV processed: {result['created']} created, {result['updated']} updated, "
                f"{len(result['errors'])} errors."
            )
        else:
            messages.error(request, "❌ Form validation failed. Please check the file.")

    return render(request, 'admin_dashboard/upload_csv.html', {
        'form': form,
        'result': result,
    })


# ─────────────────────────── UPLOAD HISTORY ───────────────────────────

@admin_required
def upload_history(request):
    uploads = CSVUpload.objects.all()
    return render(request, 'admin_dashboard/upload_history.html', {'uploads': uploads})


# ─────────────────────────── STUDENT LIST ───────────────────────────

@admin_required
def student_list(request):
    q = request.GET.get('q', '')
    branch = request.GET.get('branch', '')
    semester = request.GET.get('semester', '')

    students = StudentProfile.objects.select_related('user').order_by('-created_at')

    if q:
        students = students.filter(
            Q(name__icontains=q) |
            Q(registration_number__icontains=q) |
            Q(phone__icontains=q) |
            Q(email__icontains=q)
        )
    if branch:
        students = students.filter(branch=branch)
    if semester:
        students = students.filter(semester=semester)

    paginator = Paginator(students, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin_dashboard/students_list.html', {
        'page_obj': page_obj,
        'q': q,
        'branch': branch,
        'semester': semester,
        'branch_choices': StudentProfile.BRANCH_CHOICES,
        'semester_choices': range(1, 7),
    })


# ─────────────────────────── STUDENT EDIT ───────────────────────────

@admin_required
def student_edit(request, pk):
    profile = get_object_or_404(StudentProfile, pk=pk)
    form = StudentProfileForm(request.POST or None, instance=profile)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ {profile.name}'s profile updated successfully.")
            return redirect('student_list')
        else:
            messages.error(request, "❌ Please fix the errors below.")

    return render(request, 'admin_dashboard/student_edit.html', {
        'form': form,
        'profile': profile,
    })


# ─────────────────────────── STUDENT DELETE ───────────────────────────

@admin_required
def student_delete(request, pk):
    profile = get_object_or_404(StudentProfile, pk=pk)
    if request.method == 'POST':
        name = profile.name
        profile.user.delete()  # Cascade deletes profile
        messages.success(request, f"🗑️ Student '{name}' deleted.")
        return redirect('student_list')
    return render(request, 'admin_dashboard/student_delete_confirm.html', {'profile': profile})


# ─────────────────────────── EXPORT CSV ───────────────────────────

@admin_required
def export_students_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="students_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Registration Number', 'Name', 'Phone', 'Email', 'Branch', 'Semester',
        'Year of Admission', 'Father Name', 'Mother Name', 'Date of Birth',
        'Address', 'Password Changed', 'Created At'
    ])

    for s in StudentProfile.objects.all().order_by('branch', 'semester', 'name'):
        writer.writerow([
            s.registration_number, s.name, s.phone, s.email,
            s.get_branch_display() if s.branch else '',
            s.semester, s.year_of_admission, s.father_name, s.mother_name,
            s.date_of_birth, s.address, s.is_password_changed, s.created_at.strftime('%Y-%m-%d'),
        ])

    return response


# ─────────────────────────── CREDENTIALS MANAGEMENT ───────────────────────────

@admin_required
def export_set_password_links_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_set_password_links.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Registration Number', 'Name', 'Phone', 'Branch', 'Semester', 'Username', 'Set Password Link'
    ])

    for s in StudentProfile.objects.all().order_by('branch', 'semester', 'name'):
        writer.writerow([
            s.registration_number, s.name, s.phone,
            s.get_branch_display() if s.branch else '',
            s.semester,
            s.user.username if s.user_id else '',
            build_set_password_link(s.user) if s.user_id else '',
        ])

    return response


# ─────────────────────────── NOTICES ───────────────────────────

@admin_required
def notice_list(request):
    notices = Notice.objects.select_related("created_by", "created_by__user").all()
    return render(request, 'admin_dashboard/notices.html', {'notices': notices})


@admin_required
def notice_create(request):
    form = NoticeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        notice = form.save(commit=False)
        if hasattr(request.user, "facultyprofile"):
            notice.created_by = request.user.facultyprofile
        notice.save()
        messages.success(request, "📢 Notice published successfully.")
        return redirect('notice_list')
    return render(request, 'admin_dashboard/notice_form.html', {'form': form, 'action': 'Create'})


@admin_required
def notice_edit(request, pk):
    notice = get_object_or_404(Notice, pk=pk)
    form = NoticeForm(request.POST or None, instance=notice)
    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        if not updated.created_by_id and hasattr(request.user, "facultyprofile"):
            updated.created_by = request.user.facultyprofile
        updated.save()
        messages.success(request, "✅ Notice updated.")
        return redirect('notice_list')
    return render(request, 'admin_dashboard/notice_form.html', {'form': form, 'action': 'Edit', 'notice': notice})


@admin_required
def notice_delete(request, pk):
    notice = get_object_or_404(Notice, pk=pk)
    if request.method == 'POST':
        notice.delete()
        messages.success(request, "🗑️ Notice deleted.")
        return redirect('notice_list')
    return render(request, 'admin_dashboard/notice_delete_confirm.html', {'notice': notice})


# ─────────────────────────── SUBJECTS ───────────────────────────

@admin_required
def subject_list(request):
    subjects = Subject.objects.all().order_by('branch', 'semester', 'subject_code')
    return render(request, 'admin_dashboard/subjects.html', {'subjects': subjects})


@admin_required
def subject_create(request):
    form = SubjectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "📚 Subject created.")
        return redirect('subject_list')
    return render(request, 'admin_dashboard/subject_form.html', {'form': form, 'action': 'Create'})


@admin_required
def subject_edit(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    form = SubjectForm(request.POST or None, instance=subject)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "✅ Subject updated.")
        return redirect('subject_list')
    return render(request, 'admin_dashboard/subject_form.html', {'form': form, 'action': 'Edit', 'subject': subject})


@admin_required
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        label = f"{subject.subject_code} - {subject.subject_name}"
        subject.delete()
        messages.success(request, f"Subject '{label}' deleted.")
        return redirect('subject_list')
    related_counts = {
        "attendance": Attendance.objects.filter(subject=subject).count(),
        "marks": InternalExam.objects.filter(subject=subject).count(),
        "results": SemesterResult.objects.filter(subject=subject).count(),
        "assignments": Assignment.objects.filter(subject=subject).count(),
        "materials": StudyMaterial.objects.filter(subject=subject).count(),
        "schedules": ClassSchedule.objects.filter(subject=subject).count(),
    }
    return render(request, 'admin_dashboard/subject_delete_confirm.html', {
        'subject': subject,
        'related_counts': related_counts,
    })


# ─────────────────────────── INTERNAL MARKS ENTRY ───────────────────────────

@admin_required
def marks_entry(request):
    form = InternalExamForm(request.POST or None)
    recent_marks = InternalExam.objects.select_related('student', 'subject').order_by('-id')[:20]

    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        # Update or create
        existing = InternalExam.objects.filter(
            student=obj.student,
            subject=obj.subject,
            exam_type=obj.exam_type
        ).first()
        if existing:
            existing.marks_obtained = obj.marks_obtained
            existing.max_marks = obj.max_marks
            existing.exam_date = obj.exam_date
            existing.save()
            messages.success(request, "✅ Marks updated.")
        else:
            obj.save()
            messages.success(request, "✅ Marks saved.")
        return redirect('marks_entry')

    return render(request, 'admin_dashboard/marks_entry.html', {
        'form': form,
        'recent_marks': recent_marks,
    })


# ─────────────────────────── SEMESTER RESULTS ───────────────────────────

@admin_required
def results_view(request):
    student_id = request.GET.get('student_id')
    semester = request.GET.get('semester')
    results = []
    student = None

    if student_id:
        student = get_object_or_404(StudentProfile, pk=student_id)
        results_qs = SemesterResult.objects.filter(student=student)
        if semester:
            results_qs = results_qs.filter(semester=semester)
        results = results_qs.select_related('subject').order_by('semester', 'subject__subject_code')

    students = StudentProfile.objects.all().order_by('name')
    return render(request, 'admin_dashboard/results.html', {
        'students': students,
        'student': student,
        'results': results,
        'semester': semester,
    })


# ─────────────────────────── ATTENDANCE ENTRY ───────────────────────────

@admin_required
def attendance_entry(request):
    form = None
    if request.method == 'POST':
        from .forms import AttendanceForm
        form = AttendanceForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            att, created = Attendance.objects.get_or_create(
                student=obj.student,
                subject=obj.subject,
                date=obj.date,
                defaults={'is_present': obj.is_present, 'marked_by': obj.marked_by}
            )
            if not created:
                att.is_present = obj.is_present
                att.marked_by = obj.marked_by
                att.save()
            messages.success(request, "✅ Attendance saved.")
            return redirect('attendance_entry')
    else:
        from .forms import AttendanceForm
        form = AttendanceForm()

    recent = Attendance.objects.select_related('student', 'subject').order_by('-date', '-id')[:20]
    return render(request, 'admin_dashboard/attendance_entry.html', {'form': form, 'recent': recent})


# ─────────────────────────── BULK ATTENDANCE ENTRY ───────────────────────────

@login_required(login_url='/login/')
def take_attendance_bulk(request):
    import datetime

    if is_teacher(request.user):
        return teacher_take_attendance(request)
    if not is_admin(request.user):
        messages.error(request, "Attendance panel access is not available for this account.")
        return redirect('student_dashboard')
    
    subjects = Subject.objects.filter(is_active=True).order_by('branch', 'semester', 'subject_code')
    selected_subject_id = request.GET.get('subject') or request.POST.get('subject')
    selected_date = request.GET.get('date') or request.POST.get('date') or datetime.date.today().strftime('%Y-%m-%d')
    
    subject = None
    students = []
    attendance_records = {}
    
    if selected_subject_id:
        subject = get_object_or_404(Subject, pk=selected_subject_id)
        students = StudentProfile.objects.filter(branch=subject.branch, semester=subject.semester).order_by('registration_number')
        
        # Pre-fetch existing attendance for this date
        existing_att = Attendance.objects.filter(subject=subject, date=selected_date)
        attendance_records = {att.student_id: att for att in existing_att}
        
        present_ids = [att.student_id for att in existing_att if att.is_present]
        has_attendance = existing_att.exists()
        
    if request.method == 'POST' and subject:
        marked_by = request.user.get_full_name() or request.user.username
        
        for student in students:
            # Checkbox returns the student ID if checked
            is_present = str(student.id) in request.POST.getlist('present_student_ids')
            
            att = attendance_records.get(student.id)
            if att:
                if att.is_present != is_present:
                    att.is_present = is_present
                    att.marked_by = marked_by
                    att.save()
            else:
                Attendance.objects.create(
                    student=student,
                    subject=subject,
                    date=selected_date,
                    is_present=is_present,
                    marked_by=marked_by
                )
                
        messages.success(request, f"✅ Attendance saved for {len(students)} students in {subject.subject_code}.")
        # Keep same query params after post
        return redirect(f'/admin-panel/take-attendance/?subject={subject.id}&date={selected_date}')

    return render(request, 'admin_dashboard/take_attendance.html', {
        'subjects': subjects,
        'selected_subject': subject,
        'selected_date': selected_date,
        'students': students,
        'attendance_records': attendance_records,
        'present_ids': present_ids if 'present_ids' in locals() else [],
        'has_attendance': has_attendance if 'has_attendance' in locals() else False,
    })


# ─────────────────────────── BANNER MANAGEMENT ───────────────────────────

@login_required(login_url='/login/')
def banner_upload(request):
    if not (is_admin(request.user) or is_teacher(request.user)):
        messages.error(request, "You do not have permission to upload banners.")
        return redirect('student_dashboard')
        
    form = BannerImageForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        banner = form.save(commit=False)
        banner.uploaded_by = request.user
        banner.save()
        messages.success(request, "Banner image uploaded successfully.")
        return redirect('banner_upload')
        
    banners = BannerImage.objects.all().order_by('-created_at')
    return render(request, 'admin_dashboard/banner_upload.html', {'form': form, 'banners': banners})


@login_required(login_url='/login/')
def banner_delete(request, pk):
    if not (is_admin(request.user) or is_teacher(request.user)):
        return redirect('student_dashboard')
    banner = get_object_or_404(BannerImage, pk=pk)
    banner.delete()
    messages.success(request, "Banner deleted.")
    return redirect('banner_upload')


# ─────────────────────────── DOUBT FORUM ───────────────────────────

@login_required(login_url='/login/')
def doubt_list(request):
    doubts = Doubt.objects.select_related('student').prefetch_related('replies').all()
    form = DoubtForm()
    
    if request.method == "POST":
        if not hasattr(request.user, 'studentprofile'):
            messages.error(request, "Only students can post doubts.")
            return redirect('doubt_list')
            
        form = DoubtForm(request.POST)
        if form.is_valid():
            doubt = form.save(commit=False)
            doubt.student = request.user.studentprofile
            doubt.save()
            messages.success(request, "Your doubt has been posted to the community!")
            return redirect('doubt_list')
            
    return render(request, 'forum/doubt_list.html', {'doubts': doubts, 'form': form})


@login_required(login_url='/login/')
def doubt_detail(request, pk):
    doubt = get_object_or_404(Doubt, pk=pk)
    replies = doubt.replies.select_related('user').all()
    form = DoubtReplyForm()
    
    if request.method == "POST":
        form = DoubtReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.doubt = doubt
            reply.user = request.user
            reply.save()
            messages.success(request, "Reply posted!")
            return redirect('doubt_detail', pk=pk)
            
    return render(request, 'forum/doubt_detail.html', {'doubt': doubt, 'replies': replies, 'form': form})


# ─────────────────────────── AI CHATBOT ───────────────────────────

@login_required(login_url='/login/')
def ai_chatbot_api(request):
    if request.method == "POST":
        import json
        try:
            data = json.loads(request.body)
            prompt = data.get("prompt", "")
            
            user_context = f"User: {request.user.username}, Role: "
            if request.user.is_superuser:
                user_context += "Admin"
            elif hasattr(request.user, 'facultyprofile'):
                user_context += "Teacher"
            elif hasattr(request.user, 'studentprofile'):
                user_context += "Student"
            else:
                user_context += "Guest"
                
            response = get_ai_response(prompt, user_context)
            return JsonResponse({"response": response})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request"}, status=400)
