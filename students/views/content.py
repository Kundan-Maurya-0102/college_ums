"""Notices, banners, events, doubt forum and the AI chat endpoint."""
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

from ..pagination import paginate
from .common import *  # noqa: F401,F403
from .common import (_int_or_none, _date_or_today, _faculty_subjects,
                     _subject_class_students)


@admin_required
def notice_list(request):
    notices = paginate(request, Notice.objects.select_related("created_by", "created_by__user"))
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
    if request.method != 'POST':
        messages.error(request, "Use the delete button to remove a banner.")
        return redirect('banner_upload')
    banner.delete()
    messages.success(request, "Banner deleted.")
    return redirect('banner_upload')


@login_required(login_url='/login/')
def doubt_list(request):
    doubts = paginate(request, Doubt.objects.select_related('student').prefetch_related('replies'))
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


@login_required(login_url='/login/')
def doubt_edit(request, pk):
    doubt = get_object_or_404(Doubt, pk=pk)
    is_owner = hasattr(request.user, 'studentprofile') and doubt.student == request.user.studentprofile
    # Owner or Staff can edit/delete
    if not (is_owner or request.user.is_staff):
        messages.error(request, "You don't have permission to edit this doubt.")
        return redirect('doubt_detail', pk=pk)
    
    form = DoubtForm(request.POST or None, instance=doubt)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Doubt updated successfully.")
        return redirect('doubt_detail', pk=pk)
        
    return render(request, 'forum/doubt_form.html', {'form': form, 'doubt': doubt, 'action': 'Edit'})


@login_required(login_url='/login/')
def doubt_delete(request, pk):
    doubt = get_object_or_404(Doubt, pk=pk)
    is_owner = hasattr(request.user, 'studentprofile') and doubt.student == request.user.studentprofile
    # Owner or Staff can edit/delete
    if not (is_owner or request.user.is_staff):
        messages.error(request, "You don't have permission to delete this doubt.")
        return redirect('doubt_detail', pk=pk)
    
    if request.method == "POST":
        doubt.delete()
        messages.success(request, "Doubt deleted.")
        return redirect('doubt_list')
        
    return render(request, 'forum/doubt_confirm_delete.html', {'doubt': doubt})


@login_required(login_url='/login/')
def reply_edit(request, pk):
    reply = get_object_or_404(DoubtReply, pk=pk)
    # Owner or Staff can edit/delete
    if not (reply.user == request.user or request.user.is_staff):
        messages.error(request, "You don't have permission to edit this reply.")
        return redirect('doubt_detail', pk=reply.doubt.pk)
    
    form = DoubtReplyForm(request.POST or None, instance=reply)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Reply updated.")
        return redirect('doubt_detail', pk=reply.doubt.pk)
        
    return render(request, 'forum/reply_form.html', {'form': form, 'reply': reply})


@login_required(login_url='/login/')
def reply_delete(request, pk):
    reply = get_object_or_404(DoubtReply, pk=pk)
    doubt_pk = reply.doubt.pk
    # Owner or Staff can edit/delete
    if not (reply.user == request.user or request.user.is_staff):
        messages.error(request, "You don't have permission to delete this reply.")
        return redirect('doubt_detail', pk=doubt_pk)
    
    if request.method == "POST":
        reply.delete()
        messages.success(request, "Reply deleted.")
        return redirect('doubt_detail', pk=doubt_pk)
        
    return render(request, 'forum/reply_confirm_delete.html', {'reply': reply})


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


@admin_required
def event_list(request):
    events = paginate(request, Event.objects.all())
    return render(request, 'admin_dashboard/events.html', {'events': events})


@admin_required
def event_create(request):
    form = EventForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        event = form.save(commit=False)
        event.created_by = request.user
        event.save()
        messages.success(request, "Event created.")
        return redirect('event_list')
    return render(request, 'admin_dashboard/event_form.html', {'form': form, 'action': 'Create'})


@admin_required
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk)
    form = EventForm(request.POST or None, instance=event)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Event updated.")
        return redirect('event_list')
    return render(request, 'admin_dashboard/event_form.html', {'form': form, 'action': 'Edit'})


@admin_required
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.method == 'POST':
        event.delete()
        messages.success(request, "Event deleted.")
        return redirect('event_list')
    return render(request, 'admin_dashboard/generic_delete_confirm.html', {
        'object': event, 'object_name': str(event), 'cancel_url': 'event_list'
    })

