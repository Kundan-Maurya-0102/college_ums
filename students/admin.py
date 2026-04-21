from django.contrib import admin
from django.utils.html import format_html

from .models import (Assignment, Attendance, CSVUpload, ClassSchedule,
                     FacultyProfile, InternalExam, Notice, SemesterResult,
                     StudentProfile, StudyMaterial, Subject, WebsiteVisit)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['registration_number', 'name', 'branch', 'semester', 'phone', 'is_password_changed', 'created_at']
    list_filter = ['branch', 'semester', 'is_password_changed', 'year_of_admission']
    search_fields = ['name', 'registration_number', 'phone', 'email']
    readonly_fields = ['created_at']
    list_per_page = 30
    ordering = ['-created_at']

    fieldsets = (
        ('Login Info', {'fields': ('user', 'registration_number', 'is_password_changed')}),
        ('Personal Info', {'fields': ('name', 'phone', 'email', 'date_of_birth', 'address')}),
        ('Family Info', {'fields': ('father_name', 'mother_name')}),
        ('Academic Info', {'fields': ('branch', 'semester', 'year_of_admission')}),
        ('System', {'fields': ('created_at',)}),
    )

    def get_export_filename(self):
        return 'students_export.csv'


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['subject_code', 'subject_name', 'branch', 'semester', 'credits', 'is_active']
    list_filter = ['branch', 'semester', 'is_active']
    search_fields = ['subject_code', 'subject_name']


@admin.register(InternalExam)
class InternalExamAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'exam_type', 'marks_obtained', 'max_marks', 'exam_date']
    list_filter = ['exam_type', 'subject__branch', 'subject__semester']
    search_fields = ['student__name', 'student__registration_number']


@admin.register(SemesterResult)
class SemesterResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'semester', 'subject', 'internal_marks', 'external_marks', 'total_marks', 'grade', 'is_pass']
    list_filter = ['semester', 'grade', 'is_pass']
    search_fields = ['student__name', 'student__registration_number']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'subject', 'date', 'is_present', 'marked_by']
    list_filter = ['is_present', 'subject__branch', 'date']
    search_fields = ['student__name', 'student__registration_number']


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ['title', 'target_branches', 'target_semesters', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['title', 'content']


@admin.register(CSVUpload)
class CSVUploadAdmin(admin.ModelAdmin):
    list_display = ['description', 'uploaded_by', 'upload_date', 'is_processed', 'students_created', 'students_updated']
    readonly_fields = ['upload_date', 'is_processed', 'students_created', 'students_updated', 'errors']
    list_filter = ['is_processed']


@admin.register(FacultyProfile)
class FacultyProfileAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "department", "designation", "is_active"]
    list_filter = ["department", "is_active"]
    search_fields = ["name", "user__username", "email", "phone"]
    filter_horizontal = ["subjects"]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ["title", "subject", "assigned_by", "due_date", "is_active", "created_at"]
    list_filter = ["is_active", "subject__branch", "subject__semester"]
    search_fields = ["title", "description"]


@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ["title", "subject", "material_type", "uploaded_by", "is_active", "created_at"]
    list_filter = ["material_type", "is_active", "subject__branch", "subject__semester"]
    search_fields = ["title", "description"]


@admin.register(ClassSchedule)
class ClassScheduleAdmin(admin.ModelAdmin):
    list_display = ["subject", "faculty", "weekday", "start_time", "end_time", "room", "is_active"]
    list_filter = ["weekday", "is_active", "subject__branch", "subject__semester"]


@admin.register(WebsiteVisit)
class WebsiteVisitAdmin(admin.ModelAdmin):
    list_display = ["path", "user", "duration_seconds", "visited_at"]
    list_filter = ["visited_at"]
    search_fields = ["path", "user__username", "ip_address"]
    readonly_fields = ["path", "user", "session_key", "ip_address", "user_agent", "duration_seconds", "visited_at"]
