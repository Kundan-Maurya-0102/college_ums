from django.urls import path

from . import views
from .views_student import (
                            change_password,
                            college_website,
                            plane,
                            set_password,
                            student_certificates,
                            student_dashboard,
                            student_events,
                            student_exam_schedule,
                            student_feedback,
                            student_fees,
                            student_leave_apply,
                            student_login,
                            student_logout,
                            student_profile_edit,
)

urlpatterns = [
    # ── Ops ───────────────────────────────────────
    path('healthz/', views.healthz, name='healthz'),
    path('readyz/', views.readyz, name='readyz'),
    path('sw.js', views.service_worker, name='service_worker'),
    path('manifest.webmanifest', views.manifest, name='manifest'),
    path('offline/', views.offline, name='offline'),
    path('help/', views.help_center, name='help_center'),
    path('report-problem/', views.report_problem, name='report_problem'),

    # ── Parent / guardian portal (read-only) ──────
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    path('parent/child/<int:pk>/', views.parent_child, name='parent_child'),
    path('admin-panel/bug-reports/', views.bug_report_list, name='bug_report_list'),
    path('admin-panel/bug-reports/<int:pk>/', views.bug_report_update, name='bug_report_update'),

    # ── Legal (public) ────────────────────────────
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_use, name='terms_of_use'),

    # ── Auth ──────────────────────────────────────
    path('login/', student_login, name='student_login'),
    path('logout/', student_logout, name='student_logout'),
    path('set-password/<uidb64>/<token>/', set_password, name='set_password'),
    path('change-password/', change_password, name='change_password'),

    # ── Student Dashboard ──────────────────────────
    path('dashboard/', student_dashboard, name='student_dashboard'),
    path('profile/edit/', student_profile_edit, name='student_profile_edit'),
    path('plane/', plane, name='plane_page'),
    path('college-website/', college_website, name='college_website'),

    # ── Student: New Feature Pages ──────────────────
    path('my-fees/', student_fees, name='student_fees'),
    path('exam-schedule/', student_exam_schedule, name='student_exam_schedule'),
    path('leave-apply/', student_leave_apply, name='student_leave_apply'),
    path('feedback/', student_feedback, name='student_feedback'),
    path('events/', student_events, name='student_events'),
    path('certificates/', student_certificates, name='student_certificates'),

    # ── Admin Panel ────────────────────────────────
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/upload/', views.csv_upload, name='csv_upload'),
    path('admin-panel/upload-history/', views.upload_history, name='upload_history'),
    path('admin-panel/teachers/', views.teacher_list, name='teacher_list'),
    path('admin-panel/teachers/create/', views.teacher_create, name='teacher_create'),
    path('admin-panel/teachers/<int:pk>/edit/', views.teacher_edit, name='teacher_edit'),
    path('admin-panel/teachers/<int:pk>/delete/', views.teacher_delete, name='teacher_delete'),

    # Admin Management
    path('admin-panel/admins/', views.admin_list, name='admin_list'),
    path('admin-panel/admins/create/', views.admin_create, name='admin_create'),
    path('admin-panel/admins/<int:pk>/edit/', views.admin_edit, name='admin_edit'),
    path('admin-panel/admins/<int:pk>/delete/', views.admin_delete, name='admin_delete'),

    # Students
    path('admin-panel/students/', views.student_list, name='student_list'),
    path('admin-panel/students/add/', views.student_create, name='student_create'),
    path('admin-panel/students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('admin-panel/students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    path('admin-panel/students/<int:pk>/data-export/', views.student_data_export, name='student_data_export'),
    path('admin-panel/students/<int:pk>/anonymize/', views.student_anonymize, name='student_anonymize'),
    path('admin-panel/students/export/', views.export_students_csv, name='export_students_csv'),

    # Credentials
    path('admin-panel/credentials/export-links/', views.export_set_password_links_csv, name='export_set_password_links_csv'),

    # Notices
    path('admin-panel/notices/', views.notice_list, name='notice_list'),
    path('admin-panel/notices/create/', views.notice_create, name='notice_create'),
    path('admin-panel/notices/<int:pk>/edit/', views.notice_edit, name='notice_edit'),
    path('admin-panel/notices/<int:pk>/delete/', views.notice_delete, name='notice_delete'),

    # Subjects
    path('admin-panel/subjects/', views.subject_list, name='subject_list'),
    path('admin-panel/subjects/create/', views.subject_create, name='subject_create'),
    path('admin-panel/subjects/<int:pk>/edit/', views.subject_edit, name='subject_edit'),
    path('admin-panel/subjects/<int:pk>/delete/', views.subject_delete, name='subject_delete'),

    # Marks & Results
    path('admin-panel/marks/', views.marks_entry, name='marks_entry'),
    path('admin-panel/results/', views.results_view, name='results_view'),
    path('admin-panel/attendance/', views.attendance_entry, name='attendance_entry'),
    path('admin-panel/take-attendance/', views.take_attendance_bulk, name='take_attendance_bulk'),

    # Fees
    path('admin-panel/fees/', views.fee_structure_list, name='fee_structure_list'),
    path('admin-panel/fees/create/', views.fee_structure_create, name='fee_structure_create'),
    path('admin-panel/fees/<int:pk>/edit/', views.fee_structure_edit, name='fee_structure_edit'),
    path('admin-panel/fees/<int:pk>/delete/', views.fee_structure_delete, name='fee_structure_delete'),
    path('admin-panel/fee-payments/', views.fee_payments, name='fee_payments'),
    path('admin-panel/fee-payments/create/', views.fee_payment_create, name='fee_payment_create'),

    # Exam Schedule
    path('admin-panel/exam-schedule/', views.exam_schedule_list, name='exam_schedule_list'),
    path('admin-panel/exam-schedule/create/', views.exam_schedule_create, name='exam_schedule_create'),
    path('admin-panel/exam-schedule/<int:pk>/edit/', views.exam_schedule_edit, name='exam_schedule_edit'),
    path('admin-panel/exam-schedule/<int:pk>/delete/', views.exam_schedule_delete, name='exam_schedule_delete'),

    # Leave Applications
    path('admin-panel/leave-applications/', views.leave_applications, name='leave_applications'),
    path('admin-panel/leave-applications/<int:pk>/review/', views.leave_review, name='leave_review'),

    # Events
    path('admin-panel/events/', views.event_list, name='event_list'),
    path('admin-panel/events/create/', views.event_create, name='event_create'),
    path('admin-panel/events/<int:pk>/edit/', views.event_edit, name='event_edit'),
    path('admin-panel/events/<int:pk>/delete/', views.event_delete, name='event_delete'),

    # Feedback & Reports
    path('admin-panel/feedback/', views.feedback_report, name='feedback_report'),
    path('admin-panel/reports/', views.reports_view, name='reports_view'),

    # Teacher Panel
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/students/', views.teacher_students, name='teacher_students'),
    path('teacher/attendance/', views.teacher_take_attendance, name='teacher_take_attendance'),
    path('teacher/marks/', views.teacher_marks, name='teacher_marks'),
    path('teacher/assignments/', views.teacher_assignments, name='teacher_assignments'),
    path('teacher/materials/', views.teacher_materials, name='teacher_materials'),
    path('teacher/schedule/', views.teacher_schedule, name='teacher_schedule'),
    path('teacher/notices/', views.teacher_notices, name='teacher_notices'),
    path('teacher/notices/<int:pk>/edit/', views.teacher_notice_edit, name='teacher_notice_edit'),
    path('teacher/notices/<int:pk>/delete/', views.teacher_notice_delete, name='teacher_notice_delete'),

    # Banners (Accessible by Admin and Teachers)
    path('banners/', views.banner_upload, name='banner_upload'),
    path('banners/<int:pk>/delete/', views.banner_delete, name='banner_delete'),

    # Doubt Forum
    path('forum/', views.doubt_list, name='doubt_list'),
    path('forum/<int:pk>/', views.doubt_detail, name='doubt_detail'),
    path('forum/<int:pk>/edit/', views.doubt_edit, name='doubt_edit'),
    path('forum/<int:pk>/delete/', views.doubt_delete, name='doubt_delete'),
    path('forum/reply/<int:pk>/edit/', views.reply_edit, name='reply_edit'),
    path('forum/reply/<int:pk>/delete/', views.reply_delete, name='reply_delete'),

    # AI Chatbot
    path('api/ai-chat/', views.ai_chatbot_api, name='ai_chatbot_api'),
]
