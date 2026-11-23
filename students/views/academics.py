"""Subjects, internal marks, results, attendance and exam timetable."""
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
def subject_list(request):
    subjects = paginate(request, Subject.objects.order_by('branch', 'semester', 'subject_code'))
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


@admin_required
def results_view(request):
    student_id = _int_or_none(request.GET.get('student_id'))
    semester = _int_or_none(request.GET.get('semester'))
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


@admin_required
def attendance_entry(request):
    form = None
    if request.method == 'POST':
        from ..forms import AttendanceForm
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
        from ..forms import AttendanceForm
        form = AttendanceForm()

    recent = Attendance.objects.select_related('student', 'subject').order_by('-date', '-id')[:20]
    return render(request, 'admin_dashboard/attendance_entry.html', {'form': form, 'recent': recent})


@login_required(login_url='/login/')
def take_attendance_bulk(request):
    import datetime

    if is_teacher(request.user):
        return teacher_take_attendance(request)
    if not is_admin(request.user):
        messages.error(request, "Attendance panel access is not available for this account.")
        return redirect('student_dashboard')
    
    subjects = Subject.objects.filter(is_active=True).order_by('branch', 'semester', 'subject_code')
    selected_subject_id = _int_or_none(request.GET.get('subject') or request.POST.get('subject'))
    selected_date = _date_or_today(request.GET.get('date') or request.POST.get('date'))
    
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


@admin_required
def exam_schedule_list(request):
    schedules = ExamSchedule.objects.select_related('subject').filter(is_active=True)
    branch = request.GET.get('branch', '')
    semester = _int_or_none(request.GET.get('semester'))
    if branch:
        schedules = schedules.filter(branch=branch)
    if semester:
        schedules = schedules.filter(semester=semester)
    return render(request, 'admin_dashboard/exam_schedule.html', {
        'schedules': paginate(request, schedules),
        'branch': branch,
        'semester': semester,
        'branch_choices': StudentProfile.BRANCH_CHOICES,
    })


@admin_required
def exam_schedule_create(request):
    form = ExamScheduleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Exam schedule created.")
        return redirect('exam_schedule_list')
    return render(request, 'admin_dashboard/exam_schedule_form.html', {'form': form, 'action': 'Create'})


@admin_required
def exam_schedule_edit(request, pk):
    schedule = get_object_or_404(ExamSchedule, pk=pk)
    form = ExamScheduleForm(request.POST or None, instance=schedule)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Exam schedule updated.")
        return redirect('exam_schedule_list')
    return render(request, 'admin_dashboard/exam_schedule_form.html', {'form': form, 'action': 'Edit'})


@admin_required
def exam_schedule_delete(request, pk):
    schedule = get_object_or_404(ExamSchedule, pk=pk)
    if request.method == 'POST':
        schedule.delete()
        messages.success(request, "Exam schedule deleted.")
        return redirect('exam_schedule_list')
    return render(request, 'admin_dashboard/generic_delete_confirm.html', {
        'object': schedule, 'object_name': str(schedule), 'cancel_url': 'exam_schedule_list'
    })

