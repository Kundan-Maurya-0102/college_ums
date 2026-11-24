# Permission Matrix — College UMS

Har page dekhne ke liye authenticated session chahiye. Roles: **Admin** (`is_staff` + admin group / superuser), **Teacher** (faculty profile), **Student** (student profile). Neeche matrix automated tests se verified hai — `students/tests/test_security.py::PermissionMatrixTests`.

## Admin-only pages (`@admin_required`)

| URL | view name | Extra rule |
|---|---|---|
| `/admin-panel/` | `admin_dashboard` | — |
| `/admin-panel/admins/` | `admin_list` | — |
| `/admin-panel/admins/<int:pk>/delete/` | `admin_delete` | — |
| `/admin-panel/admins/<int:pk>/edit/` | `admin_edit` | — |
| `/admin-panel/admins/create/` | `admin_create` | — |
| `/admin-panel/attendance/` | `attendance_entry` | — |
| `/admin-panel/credentials/export-links/` | `export_set_password_links_csv` | Admin-only; links expire in PASSWORD_TOKEN_TIMEOUT_HOURS |
| `/admin-panel/events/` | `event_list` | — |
| `/admin-panel/events/<int:pk>/delete/` | `event_delete` | — |
| `/admin-panel/events/<int:pk>/edit/` | `event_edit` | — |
| `/admin-panel/events/create/` | `event_create` | — |
| `/admin-panel/exam-schedule/` | `exam_schedule_list` | — |
| `/admin-panel/exam-schedule/<int:pk>/delete/` | `exam_schedule_delete` | — |
| `/admin-panel/exam-schedule/<int:pk>/edit/` | `exam_schedule_edit` | — |
| `/admin-panel/exam-schedule/create/` | `exam_schedule_create` | — |
| `/admin-panel/fee-payments/` | `fee_payments` | Admin sees all payments |
| `/admin-panel/fee-payments/create/` | `fee_payment_create` | — |
| `/admin-panel/feedback/` | `feedback_report` | — |
| `/admin-panel/fees/` | `fee_structure_list` | — |
| `/admin-panel/fees/<int:pk>/delete/` | `fee_structure_delete` | — |
| `/admin-panel/fees/<int:pk>/edit/` | `fee_structure_edit` | — |
| `/admin-panel/fees/create/` | `fee_structure_create` | — |
| `/admin-panel/leave-applications/` | `leave_applications` | — |
| `/admin-panel/leave-applications/<int:pk>/review/` | `leave_review` | — |
| `/admin-panel/marks/` | `marks_entry` | — |
| `/admin-panel/notices/` | `notice_list` | — |
| `/admin-panel/notices/<int:pk>/delete/` | `notice_delete` | — |
| `/admin-panel/notices/<int:pk>/edit/` | `notice_edit` | — |
| `/admin-panel/notices/create/` | `notice_create` | — |
| `/admin-panel/reports/` | `reports_view` | — |
| `/admin-panel/results/` | `results_view` | — |
| `/admin-panel/students/` | `student_list` | — |
| `/admin-panel/students/<int:pk>/delete/` | `student_delete` | — |
| `/admin-panel/students/<int:pk>/edit/` | `student_edit` | — |
| `/admin-panel/students/export/` | `export_students_csv` | Admin-only export of all students |
| `/admin-panel/subjects/` | `subject_list` | — |
| `/admin-panel/subjects/<int:pk>/delete/` | `subject_delete` | — |
| `/admin-panel/subjects/<int:pk>/edit/` | `subject_edit` | — |
| `/admin-panel/subjects/create/` | `subject_create` | — |
| `/admin-panel/teachers/` | `teacher_list` | — |
| `/admin-panel/teachers/<int:pk>/delete/` | `teacher_delete` | — |
| `/admin-panel/teachers/<int:pk>/edit/` | `teacher_edit` | — |
| `/admin-panel/teachers/create/` | `teacher_create` | — |
| `/admin-panel/upload-history/` | `upload_history` | — |
| `/admin-panel/upload/` | `csv_upload` | — |

## Teacher pages (`@teacher_required`)

| URL | view name | Extra rule |
|---|---|---|
| `/teacher/` | `teacher_dashboard` | — |
| `/teacher/assignments/` | `teacher_assignments` | — |
| `/teacher/attendance/` | `teacher_take_attendance` | — |
| `/teacher/marks/` | `teacher_marks` | — |
| `/teacher/materials/` | `teacher_materials` | — |
| `/teacher/notices/` | `teacher_notices` | — |
| `/teacher/notices/<int:pk>/delete/` | `teacher_notice_delete` | — |
| `/teacher/notices/<int:pk>/edit/` | `teacher_notice_edit` | — |
| `/teacher/schedule/` | `teacher_schedule` | — |
| `/teacher/students/` | `teacher_students` | — |

## Any logged-in user (`@login_required`, with internal checks)

| URL | view name | Extra rule |
|---|---|---|
| `/admin-panel/take-attendance/` | `take_attendance_bulk` | Internal check: admin can any subject, teacher only own subjects; students redirected |
| `/api/ai-chat/` | `ai_chatbot_api` | JSON API, 20 msgs / 5 min per user+IP, no error details leaked |
| `/banners/` | `banner_upload` | Internal check: admin or teacher only |
| `/banners/<int:pk>/delete/` | `banner_delete` | Internal check: admin or teacher only; POST required |
| `/forum/` | `doubt_list` | — |
| `/forum/<int:pk>/` | `doubt_detail` | — |
| `/forum/<int:pk>/delete/` | `doubt_delete` | Object rule: only the author can delete |
| `/forum/<int:pk>/edit/` | `doubt_edit` | Object rule: only the author can edit |
| `/forum/reply/<int:pk>/delete/` | `reply_delete` | Object rule: reply author or staff |
| `/forum/reply/<int:pk>/edit/` | `reply_edit` | Object rule: reply author or staff |
| `/healthz/` | `healthz` | Public, DB-free probe |

## Public pages

| URL | view name | Notes |
|---|---|---|
| `/` | `home` | Landing page; env branding |
| `/login/` | `student_login` | Brute-force lockout after `LOGIN_MAX_ATTEMPTS` |
| `/logout/` | `student_logout` | Session flush |
| `/set-password/<uid>/<token>/` | `set_password` | One-time token, `PASSWORD_TOKEN_TIMEOUT_HOURS` |
| `/healthz/` | `healthz` | DB-free probe, not visit-logged |
| `/college-website/`, `/about/`, `/contact/` | static content pages | Read-only |

## Roles and how they are checked

| Role | Flag / relation | Guard |
|---|---|---|
| Admin | `user.is_staff` (and superuser) | `students/decorators.py: admin_required` |
| Teacher | `user.staffprofile` / `user.facultyprofile` | `students/decorators.py: teacher_required` |
| Student | `user.studentprofile` | `students/decorators.py: student_required` |
| Parent (read-only) | not implemented yet | planned in Phase 7 |

Admin/teacher/student mix-ups are covered by tests: a student hitting an admin URL gets 302/403 and never 200, and the same in every other direction.

## Object-level rules (IDOR)

| Model | Rule |
|---|---|
| `StudentProfile` | Admin only; student sees only `request.user.studentprofile` |
| `FeePayment` | Admin writes; student reads own rows only |
| `Doubt` / `DoubtReply` | Author edits/deletes own; staff can moderate |
| `LeaveApplication` | Student creates/reads own; admin reviews |
| `Certificate` | Generated from own profile only |
| `Assignment` / `StudyMaterial` | Teacher (own subject) uploads; any logged-in student reads |
| `AuditLog` | Admin read-only, never editable through UI |

