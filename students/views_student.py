from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_decode

from .forms import CustomPasswordChangeForm, StudentSelfProfileForm
from .models import (Assignment, Attendance, ClassSchedule, InternalExam,
                     Notice, SemesterResult, StudentProfile, StudyMaterial,
                     Subject)
from .password_links import token_generator

def plane(request):
    return render(request, 'plane.html')

    

def student_login(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            if hasattr(request.user, "facultyprofile") and not request.user.is_superuser:
                return redirect('teacher_dashboard')
            return redirect('admin_dashboard')
        return redirect('student_dashboard')

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_staff:
                if hasattr(user, "facultyprofile") and not user.is_superuser:
                    return redirect('teacher_dashboard')
                return redirect('admin_dashboard')
            # Force password change check
            try:
                profile = user.studentprofile
                if not profile.is_password_changed:
                    messages.warning(request, "⚠️ Please change your default password to secure your account.")
                    return redirect('change_password')
            except StudentProfile.DoesNotExist:
                pass
            return redirect('student_dashboard')
        else:
            messages.error(request, "❌ Invalid username or password.")

    return render(request, 'student/login.html', {'form': form})


def student_logout(request):
    logout(request)
    return redirect('student_login')


@login_required(login_url='/login/')
def change_password(request):
    form = CustomPasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            # Mark password as changed
            try:
                profile = user.studentprofile
                profile.is_password_changed = True
                profile.save()
            except StudentProfile.DoesNotExist:
                pass
            messages.success(request, "🔐 Password changed successfully!")
            if request.user.is_staff:
                if hasattr(request.user, "facultyprofile") and not request.user.is_superuser:
                    return redirect('teacher_dashboard')
                return redirect('admin_dashboard')
            return redirect('student_dashboard')
        else:
            messages.error(request, "❌ Please fix the errors below.")

    return render(request, 'student/change_password.html', {'form': form})


def set_password(request, uidb64, token):
    """
    Public set-password flow using a signed one-time token.
    This replaces exporting/storing plaintext passwords.
    """
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except Exception:
        user = None

    if not user or not token_generator.check_token(user, token):
        messages.error(request, "This set-password link is invalid or expired. Please contact admin for a new link.")
        return redirect("student_login")

    form = SetPasswordForm(user, request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            # Mark profile as password changed if this is a student user
            try:
                profile = user.studentprofile
                profile.is_password_changed = True
                profile.save()
            except StudentProfile.DoesNotExist:
                pass
            messages.success(request, "Password set successfully. Please login.")
            return redirect("student_login")
        messages.error(request, "Please fix the errors below.")

    return render(request, "student/set_password.html", {"form": form, "username": user.username})


@login_required(login_url='/login/')
def student_dashboard(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')

    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile found for your account.")
        return redirect('student_login')

    # Force password change
    if not profile.is_password_changed:
        messages.warning(request, "⚠️ Please change your default password first.")
        return redirect('change_password')

    # Get subjects for this branch/semester
    subjects = Subject.objects.filter(
        branch=profile.branch,
        semester=profile.semester,
        is_active=True
    ) if profile.branch and profile.semester else []

    # Internal Marks
    internal_marks = {}
    if subjects:
        marks_qs = InternalExam.objects.filter(
            student=profile
        ).select_related('subject')
        for mark in marks_qs:
            key = mark.subject.subject_code
            if key not in internal_marks:
                internal_marks[key] = {'subject': mark.subject, 'marks': {}}
            internal_marks[key]['marks'][mark.exam_type] = {
                'obtained': mark.marks_obtained,
                'max': mark.max_marks,
                'pct': mark.percentage(),
            }

    # Semester Results
    results = SemesterResult.objects.filter(
        student=profile
    ).select_related('subject').order_by('semester', 'subject__subject_code')

    results_by_sem = {}
    for r in results:
        if r.semester not in results_by_sem:
            results_by_sem[r.semester] = []
        results_by_sem[r.semester].append(r)

    # Attendance per subject
    attendance_data = []
    for subject in subjects:
        total = Attendance.objects.filter(student=profile, subject=subject).count()
        present = Attendance.objects.filter(student=profile, subject=subject, is_present=True).count()
        pct = round((present / total) * 100, 1) if total > 0 else 0
        attendance_data.append({
            'subject': subject,
            'total': total,
            'present': present,
            'absent': total - present,
            'percentage': pct,
            'status': 'danger' if pct < 75 else ('warning' if pct < 85 else 'success'),
        })

    # Notices for this student
    all_notices = Notice.objects.filter(is_active=True)
    notices = [n for n in all_notices if n.is_for_student(profile)]

    exam_types = ['CA1', 'CA2', 'CA3', 'MSE', 'ASSIGNMENT']
    assignments = Assignment.objects.filter(subject__in=subjects, is_active=True).select_related("subject", "assigned_by")[:10]
    materials = StudyMaterial.objects.filter(subject__in=subjects, is_active=True).select_related("subject", "uploaded_by")[:10]
    schedules = ClassSchedule.objects.filter(subject__in=subjects, is_active=True).select_related("subject", "faculty")
    teachers = []
    for subject in subjects:
        for faculty in subject.faculty.filter(is_active=True):
            teachers.append({"subject": subject, "faculty": faculty})

    context = {
        'profile': profile,
        'subjects': subjects,
        'internal_marks': internal_marks,
        'results_by_sem': results_by_sem,
        'attendance_data': attendance_data,
        'notices': notices,
        'exam_types': exam_types,
        'assignments': assignments,
        'materials': materials,
        'schedules': schedules,
        'teachers': teachers,
    }
    return render(request, 'student/dashboard.html', context)


@login_required(login_url="/login/")
def student_profile_edit(request):
    if request.user.is_staff:
        return redirect("admin_dashboard")
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile found for your account.")
        return redirect("student_login")

    if not profile.is_password_changed:
        messages.warning(request, "⚠️ Please change your default password first.")
        return redirect("change_password")

    form = StudentSelfProfileForm(request.POST or None, instance=profile)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Profile updated successfully.")
            return redirect("student_dashboard")
        messages.error(request, "❌ Please fix the errors below.")

    return render(request, "student/profile_edit.html", {"form": form, "profile": profile})


@login_required(login_url='/login/')
def college_website(request):
    return render(request, 'student/college_website.html')
