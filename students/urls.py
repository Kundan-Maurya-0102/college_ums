from django.urls import path
from . import views
from .views_student import student_login, student_logout, change_password, student_dashboard, plane, college_website, set_password, student_profile_edit

urlpatterns = [
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
    # ── Admin Panel ────────────────────────────────
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/upload/', views.csv_upload, name='csv_upload'),
    path('admin-panel/upload-history/', views.upload_history, name='upload_history'),
    path('admin-panel/teachers/', views.teacher_list, name='teacher_list'),
    path('admin-panel/teachers/create/', views.teacher_create, name='teacher_create'),
    path('admin-panel/teachers/<int:pk>/edit/', views.teacher_edit, name='teacher_edit'),
    path('admin-panel/teachers/<int:pk>/delete/', views.teacher_delete, name='teacher_delete'),

    # Students
    path('admin-panel/students/', views.student_list, name='student_list'),
    path('admin-panel/students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('admin-panel/students/<int:pk>/delete/', views.student_delete, name='student_delete'),
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
]
