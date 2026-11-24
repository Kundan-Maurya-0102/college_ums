"""Teacher, admin and student account management + CSV exports."""
import csv
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..audit import log_action
from ..forms import (
    AdminUserForm,
    FacultyProfileForm,
    StudentProfileForm,
)
from ..models import (
    Assignment,
    ClassSchedule,
    FacultyProfile,
    InternalExam,
    StudentProfile,
    StudyMaterial,
)
from ..pagination import paginate
from ..password_links import build_set_password_link
from ..privacy import anonymize_student
from .common import _int_or_none, admin_required


@admin_required
def teacher_list(request):
    teachers = paginate(request, FacultyProfile.objects.select_related("user").prefetch_related("subjects").order_by("name"))
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


@admin_required
def admin_list(request):
    admins = User.objects.filter(is_staff=True).exclude(facultyprofile__isnull=False).order_by("username")
    return render(request, "admin_dashboard/admins.html", {"admins": paginate(request, admins)})


@admin_required
def admin_create(request):
    form = AdminUserForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            admin_user = form.save()
            messages.success(request, f"Admin account '{admin_user.username}' created successfully.")
            return redirect("admin_list")
        messages.error(request, "Please fix the errors below.")
    return render(request, "admin_dashboard/admin_form.html", {"form": form, "action": "Create"})


@admin_required
def admin_edit(request, pk):
    admin_user = get_object_or_404(User, pk=pk, is_staff=True)
    form = AdminUserForm(request.POST or None, instance=admin_user)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, f"Admin account '{admin_user.username}' updated.")
            return redirect("admin_list")
        messages.error(request, "Please fix the errors below.")
    return render(request, "admin_dashboard/admin_form.html", {"form": form, "admin_user": admin_user, "action": "Edit"})


@admin_required
def admin_delete(request, pk):
    admin_user = get_object_or_404(User, pk=pk, is_staff=True)
    if admin_user == request.user:
        messages.error(request, "You cannot delete your own logged-in admin account.")
        return redirect("admin_list")

    if request.method == "POST":
        username = admin_user.username
        admin_user.delete()
        messages.success(request, f"Admin account '{username}' deleted.")
        return redirect("admin_list")

    return render(request, "admin_dashboard/admin_delete_confirm.html", {"admin_user": admin_user})


@admin_required
def student_list(request):
    q = request.GET.get('q', '')
    branch = request.GET.get('branch', '')
    semester = _int_or_none(request.GET.get('semester'))

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


@admin_required
def student_edit(request, pk):
    profile = get_object_or_404(StudentProfile, pk=pk)
    form = StudentProfileForm(request.POST or None, instance=profile)

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            log_action(request, "student.update", profile, detail=profile.registration_number)
            messages.success(request, f"✅ {profile.name}'s profile updated successfully.")
            return redirect('student_list')
        else:
            messages.error(request, "❌ Please fix the errors below.")

    return render(request, 'admin_dashboard/student_edit.html', {
        'form': form,
        'profile': profile,
    })


@admin_required
def student_delete(request, pk):
    profile = get_object_or_404(StudentProfile, pk=pk)
    if request.method == 'POST':
        name = profile.name
        log_action(request, "student.delete", profile, detail=f"{name} / {profile.registration_number}")
        profile.user.delete()  # Cascade deletes profile
        messages.success(request, f"🗑️ Student '{name}' deleted.")
        return redirect('student_list')
    return render(request, 'admin_dashboard/student_delete_confirm.html', {'profile': profile})


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



@admin_required
def student_data_export(request, pk):
    """Download one student's personal data as JSON (privacy/GDPR style access request)."""
    profile = get_object_or_404(StudentProfile, pk=pk)
    log_action(request, "student.data_export", profile,
               detail="full personal data export requested")

    def iso(value):
        return value.isoformat() if value else None

    data = {
        "exported_at": timezone.now().isoformat(),
        "college": getattr(settings, "COLLEGE_NAME", ""),
        "profile": {
            "name": profile.name,
            "registration_number": profile.registration_number,
            "branch": profile.get_branch_display_name(),
            "semester": profile.semester,
            "year_of_admission": profile.year_of_admission,
            "phone": profile.phone,
            "email": profile.email,
            "address": profile.address,
            "father_name": profile.father_name,
            "mother_name": profile.mother_name,
            "date_of_birth": iso(profile.date_of_birth),
            "consent_given_at": iso(profile.consent_given_at),
            "created_at": iso(profile.created_at),
        },
        "attendance": list(profile.attendance_set.values(
            "date", "subject__subject_code", "is_present")),
        "internal_marks": list(InternalExam.objects.filter(student=profile).values(
            "subject__subject_code", "exam_type", "marks_obtained", "max_marks", "exam_date")),
        "fee_payments": list(profile.fee_payments.values(
            "fee_structure__fee_type", "amount_paid", "payment_date", "status",
            "receipt_number", "payment_mode")),
        "leave_applications": list(profile.leave_applications.values(
            "from_date", "to_date", "reason", "status")),
        "feedback": list(profile.feedbacks.values("subject__subject_code", "rating", "comments", "created_at")),
        "doubts": list(profile.doubts.values("title", "content", "created_at")),
    }

    response = HttpResponse(
        json.dumps(data, indent=2, default=str),
        content_type="application/json",
    )
    filename = f"student-{profile.registration_number}-data-{timezone.now():%Y%m%d}.json"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


@admin_required
def student_anonymize(request, pk):
    """Erase a student's personal identifiers but keep academic/financial records.

    GET shows exactly what will be removed/kept; POST performs the anonymisation.
    """
    profile = get_object_or_404(StudentProfile, pk=pk)
    if request.method == "POST":
        if request.POST.get("confirm") != "yes":
            messages.error(request, "Please tick the confirmation box to anonymise this record.")
            return redirect("student_anonymize", pk=profile.pk)

        reg_no = anonymize_student(profile)
        log_action(request, "student.anonymize", profile,
                   detail=f"personal data erased, academic records kept (reg {reg_no})")
        messages.success(request, "Personal data erased. Academic and fee records kept for the college archive.")
        return redirect("student_list")

    return render(request, "admin_dashboard/student_privacy.html", {"profile": profile})


@admin_required
def student_create(request):
    """Add one student by hand (the CSV upload is still the bulk path).

    Creates the login too: username = registration number, unusable password until
    the office sends a set-password link, exactly like an imported student.
    """
    form = StudentProfileForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        profile = form.save(commit=False)
        user = User.objects.create_user(
            username=profile.registration_number,
            email=profile.email or '',
            password=None,          # unusable until the set-password link is used
        )
        user.set_unusable_password()
        user.save(update_fields=['password'])
        profile.user = user
        profile.is_password_changed = False
        profile.save()
        log_action(request, 'student.create', profile, detail=profile.registration_number)
        messages.success(
            request,
            f"✅ {profile.name} added. Username: {profile.registration_number}. "
            "Send the set-password link from All Students → Set-password links."
        )
        return redirect('student_list')
    if request.method == 'POST':
        messages.error(request, "❌ Please fix the errors below.")

    return render(request, 'admin_dashboard/student_form.html', {
        'form': form,
        'page_title': 'Add student',
    })
