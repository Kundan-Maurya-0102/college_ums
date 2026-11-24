"""Helpers shared by every view module: role checks, decorators, health probe."""
import csv
import datetime
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..ai_helper import get_ai_response
from ..upload_router import process_any_csv_upload
from ..password_links import build_set_password_link
from ..forms import (AssignmentForm, BannerImageForm, CSVUploadForm, ClassScheduleForm,
                    DoubtForm, DoubtReplyForm, EventForm, ExamScheduleForm,
                    FacultyProfileForm, FeedbackForm, FeePaymentForm,
                    FeeStructureForm, InternalExamForm, LeaveApplicationForm,
                    NoticeForm, StudentProfileForm, StudyMaterialForm, SubjectForm,
                    AdminUserForm)
from ..models import (Assignment, Attendance, BannerImage, CSVUpload, ClassSchedule,
                     Doubt, DoubtReply, Event, ExamSchedule, FacultyProfile,
                     Feedback, FeePayment, FeeStructure, InternalExam,
                     LeaveApplication, Notice, SemesterResult, StudentProfile,
                     StudyMaterial, Subject, WebsiteVisit)


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


def _int_or_none(value):
    """Return an int for valid form/query values, otherwise None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _date_or_today(value):
    """Parse an ISO date from a query/form value, falling back to today."""
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.date.today()


def _faculty_subjects(user):
    return user.facultyprofile.subjects.filter(is_active=True).order_by("branch", "semester", "subject_code")


def _subject_class_students(subject):
    return StudentProfile.objects.filter(branch=subject.branch, semester=subject.semester).order_by("registration_number")


def healthz(request):
    """Liveness probe for Docker/Caddy. No DB access, no auth, not visit-logged."""
    return JsonResponse({"status": "ok"})



def service_worker(request):
    """Serve the PWA service worker from the site root so its scope is "/".

    Rendered through a template because static file names are hashed by
    ManifestStaticFilesStorage in production.
    """
    response = render(request, 'sw.js', content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


def offline(request):
    """Static fallback page shown by the service worker when the network is down."""
    return render(request, 'offline.html')


def manifest(request):
    """Per-college web app manifest (name/colors come from env branding)."""
    from django.conf import settings

    name = getattr(settings, 'COLLEGE_NAME', '') or 'College UMS'
    short_name = (name.split('(')[0].strip() or 'UMS')[:12]
    # Unhashed static URLs: WhiteNoise serves the originals too, and manifest
    # icon URLs must stay stable for installed apps.
    static_url = settings.STATIC_URL or '/static/'
    if not static_url.endswith('/'):
        static_url += '/'

    def icon(path):
        return f"{static_url}{path}"
    data = {
        "name": f"{name} UMS",
        "short_name": short_name,
        "description": f"{name} — attendance, marks, fees and notices.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#f6f8fb",
        "theme_color": getattr(settings, 'PRIMARY_COLOR', '#1d4ed8') or '#1d4ed8',
        "icons": [
            {"src": icon('images/icon-192.png'), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": icon('images/icon-512.png'), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": icon('images/icon-maskable-512.png'), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    response = JsonResponse(data, json_dumps_params={'indent': 2})
    response['Content-Type'] = 'application/manifest+json'
    return response
