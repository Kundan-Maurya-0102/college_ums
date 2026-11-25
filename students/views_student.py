from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.models import User
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode

from . import dashboard_data
from .forms import CustomPasswordChangeForm, FeedbackForm, LeaveApplicationForm, StudentSelfProfileForm
from .models import (
    BannerImage,
    DashboardSettings,
    Event,
    ExamSchedule,
    FacultyProfile,
    Feedback,
    FeePayment,
    FeeStructure,
    LeaveApplication,
    StudentProfile,
    Subject,
)
from .password_links import token_generator
from .security import login_lockout_remaining, register_login_failure, reset_login_failures


def plane(request):
    return render(request, 'student/plane.html')



def student_login(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            if hasattr(request.user, "facultyprofile") and not request.user.is_superuser:
                return redirect('teacher_dashboard')
            return redirect('admin_dashboard')
        if hasattr(request.user, "studentprofile"):
            return redirect('student_dashboard')
        if getattr(request.user, "guardianprofile", None) and request.user.guardianprofile.is_active:
            return redirect('parent_dashboard')
        # Authenticated account without a student profile would otherwise
        # bounce between /login/ and /dashboard/ forever.
        logout(request)
        messages.error(request, "No student profile is linked to this account. Please contact the admin.")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        username = request.POST.get('username', '')
        locked_for = login_lockout_remaining(request, username)
        if locked_for:
            wait_minutes = max(1, locked_for // 60)
            messages.error(
                request,
                f"🔒 Account locked for {wait_minutes} minute(s) after too many wrong "
                "passwords. Your password may still be correct — wait for the timer, or ask "
                "the college office for a set-password link if you have forgotten it.",
            )
            return render(request, 'student/login.html', {
                'form': form,
                'lockout_seconds': int(locked_for),
            })

        if form.is_valid():
            user = form.get_user()
            reset_login_failures(request, username)
            login(request, user)
            profile = getattr(user, 'studentprofile', None)
            if profile is not None and profile.consent_given_at is None:
                profile.consent_given_at = timezone.now()
                profile.save(update_fields=['consent_given_at'])
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
            guardian = getattr(user, "guardianprofile", None)
            if guardian and guardian.is_active and not hasattr(user, "studentprofile"):
                return redirect('parent_dashboard')
            return redirect('student_dashboard')
        else:
            remaining = register_login_failure(request, username)
            left = max(0, getattr(settings, "LOGIN_MAX_ATTEMPTS", 5) - remaining)
            if left:
                messages.error(
                    request,
                    f"❌ Username or password is incorrect. {left} attempt(s) left before a "
                    f"{getattr(settings, 'LOGIN_LOCKOUT_MINUTES', 15)}-minute lock."
                    + (" Forgotten password? Ask the office for a set-password link."
                       if left <= 2 else ""),
                )
            else:
                messages.error(
                    request,
                    "🔒 Too many wrong attempts — the login is locked for "
                    f"{getattr(settings, 'LOGIN_LOCKOUT_MINUTES', 15)} minute(s). "
                    "Wait, or ask the office for a set-password link.",
                )

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
    """The whole student view on one screen.

    Data comes from `students.dashboard_data.build` (aggregate queries only, scoped to
    this student). The layout is `student/dashboard.html` on the `student/shell.html`
    chrome: top navbar, collapsible sidebar, quick links, card grid.
    """
    if request.user.is_staff:
        return redirect('admin_dashboard')

    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile found for your account.")
        return redirect('student_login')

    # Force password change (and keep the banner honest about it).
    if not profile.is_password_changed:
        messages.warning(request, "⚠️ Please change your default password first.")
        return redirect('change_password')

    settings_obj = DashboardSettings.load()
    cards = {key: settings_obj.is_card_visible(key)
             for key, _label in DashboardSettings.CARD_CHOICES}
    query = (request.GET.get('q') or '').strip()[:60]
    context = dashboard_data.build(
        profile,
        gateway_configured=bool(getattr(settings, 'RAZORPAY_KEY_ID', '')),
        cards=cards,
        query=query,
    )
    read_state = profile.dashboard_seen_at     # computed before marking, for the dots
    dashboard_data.mark_seen(profile)

    context.update({
        'profile': profile,
        'dashboard_settings': settings_obj,
        'quick_links': dashboard_data.DEFAULT_QUICK_LINKS,
        'read_state': read_state,
        'banners': BannerImage.objects.filter(is_active=True),
        'today': timezone.localdate(),
        # kept for templates/tests that still read the flat lists
        'subjects': [row['subject'] for row in context['course_rows']],
        'notices': [entry['notice'] for entry in context['announcements']],
    })
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
    return render(request, 'student/college_website.html', {
        'branch_count': len(StudentProfile.BRANCH_CHOICES),
    })


# ─────────────────── STUDENT: FEE STATUS ───────────────────

@login_required(login_url='/login/')
def student_fees(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        return redirect('student_login')

    # Get fee structures for this student's branch/semester
    structures = FeeStructure.objects.filter(
        branch=profile.branch, is_active=True
    ).order_by('semester', 'fee_type') if profile.branch else []

    # Get payments made by this student
    payments = FeePayment.objects.filter(student=profile).select_related('fee_structure')
    total_paid = payments.filter(status='PAID').aggregate(total=Sum('amount_paid'))['total'] or 0

    return render(request, 'student/fees.html', {
        'profile': profile,
        'structures': structures,
        'payments': payments,
        'total_paid': total_paid,
    })


# ─────────────────── STUDENT: EXAM SCHEDULE ───────────────────

@login_required(login_url='/login/')
def student_exam_schedule(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        return redirect('student_login')

    schedules = ExamSchedule.objects.filter(
        branch=profile.branch, semester=profile.semester, is_active=True
    ).select_related('subject') if profile.branch and profile.semester else []

    return render(request, 'student/exam_schedule.html', {
        'profile': profile,
        'schedules': schedules,
    })


# ─────────────────── STUDENT: LEAVE APPLICATION ───────────────────

@login_required(login_url='/login/')
def student_leave_apply(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        return redirect('student_login')

    form = LeaveApplicationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        leave = form.save(commit=False)
        leave.student = profile
        leave.save()
        messages.success(request, "Leave application submitted.")
        return redirect('student_leave_apply')

    my_leaves = LeaveApplication.objects.filter(student=profile)
    return render(request, 'student/leave_apply.html', {
        'profile': profile,
        'form': form,
        'my_leaves': my_leaves,
    })


# ─────────────────── STUDENT: FEEDBACK ───────────────────

@login_required(login_url='/login/')
def student_feedback(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        return redirect('student_login')

    subjects = Subject.objects.filter(
        branch=profile.branch, semester=profile.semester, is_active=True
    ) if profile.branch and profile.semester else Subject.objects.none()

    form = FeedbackForm(request.POST or None)
    form.fields['subject'].queryset = subjects
    form.fields['faculty'].queryset = FacultyProfile.objects.filter(
        subjects__in=subjects, is_active=True
    ).distinct()

    if request.method == 'POST' and form.is_valid():
        feedback = form.save(commit=False)
        feedback.student = profile
        feedback.semester = profile.semester or 1
        Feedback.objects.update_or_create(
            student=profile,
            subject=feedback.subject,
            semester=feedback.semester,
            defaults={
                'faculty': feedback.faculty,
                'rating': feedback.rating,
                'comments': feedback.comments,
            },
        )
        messages.success(request, "Feedback submitted. Thank you!")
        return redirect('student_feedback')

    existing = Feedback.objects.filter(student=profile, semester=profile.semester)
    return render(request, 'student/feedback.html', {
        'profile': profile,
        'form': form,
        'existing': existing,
    })


# ─────────────────── STUDENT: EVENTS / CALENDAR ───────────────────

@login_required(login_url='/login/')
def student_events(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')

    events = Event.objects.filter(is_active=True)
    return render(request, 'student/events.html', {'events': events})


# ─────────────────── STUDENT: CERTIFICATES ───────────────────

@login_required(login_url='/login/')
def student_certificates(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    try:
        profile = request.user.studentprofile
    except StudentProfile.DoesNotExist:
        return redirect('student_login')

    cert_type = request.GET.get('type', '')
    return render(request, 'student/certificates.html', {
        'profile': profile,
        'cert_type': cert_type,
    })

