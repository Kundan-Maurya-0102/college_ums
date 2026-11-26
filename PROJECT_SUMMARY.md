# PROJECT_SUMMARY.md — College UMS (Senior Engineer First-Impression Audit)

*Yeh summary asli source code, models, urls, views, settings, tests aur deploy files se likha gaya hai. PROGRESS.md ya purane reports par bharosa nahi kiya gaya. Jo cheez code mein verify nahi ho sakti, uske saath "verify nahi hua" likha gaya hai. Koi andaaza nahi lagaya.*

---

## 1. Project kya hai

**College UMS** ek Django 5.2.19 based College Management System hai. Iska maqsad ek hi codebase se kai alag-alag colleges ko serve karna hai, jiske liye har college ka alag deployment hota hai (alag domain, alag database, alag `.env` file). Code mein koi college-specific cheez hardcoded nahi hai — sab branding `.env` se aati hai.

**Target audience (roles):**
- **Student** — apni attendance, marks, fees, timetable, notices, exam documents (hall ticket/marksheet), leave apply, feedback, profile edit
- **Teacher (Faculty)** — apne subjects ke students, attendance marking, marks entry, notices, materials, assignments, schedule
- **Admin (Office Staff)** — student/teacher/admin account management, CSV bulk import, marks/attendance entry, fee collection, notices, events, reports, exam documents bulk generate
- **Parent / Guardian** — read-only view of linked children's attendance, marks, fees, notices
- **Super Admin / Platform Admin** — multi-college dashboard, college onboarding, plans, subscriptions, suspend/resume, support tickets, metrics

File path: `students/models.py`, `students/urls.py`, `college_ums/settings.py`

---

## 2. Architecture

### Apps / Modules

| App | Kaam |
|-----|------|
| `students` | Main business logic: sab models, views, forms, templates, management commands, background tasks, middleware |
| `platform_admin` | Super admin panel: colleges, plans, subscriptions, support tickets, usage metrics |
| `college_ums` (project package) | Settings, root URLs, WSGI/ASGI |

### Request Flow

```
Browser → Caddy (reverse proxy, TLS termination) → Gunicorn → Django
                                ↓
                        college_ums/urls.py → students/urls.py
                                ↓
                        View (role-checked decorator: @admin_required / @teacher_required / @login_required)
                                ↓
                        Model query (scoped to current college's DB only)
                                ↓
                        Template render → HTML response
```

### Multi-College kaise chalta hai

**Ek codebase, alag deployment.** Har college ka apna `.env`, apna database (SQLite ya PostgreSQL), apna domain. `COLLEGE_SLUG` env variable se pehchaan hota hai ki yeh kaunsa college ka deployment hai. `platform_admin.middleware.SubscriptionStatusMiddleware` check karta hai ki college suspended ya expired hai toh writes block kar deta hai (read-only mode).

Data isolation code-level se nahi, deployment-level se hai: College A ka deployment College B ki database kabhi nahi chua. Yeh `students/tests/test_isolation.py` mein verify kiya gaya hai (verify nahi hua par test file mojood hai).

Verify status: **Verified via code review** — settings.py mein `DATABASES` sirf ek `default` alias hai, koi multi-DB routing nahi hai.


---

## 3. Tech Stack aur Exact Versions

| Layer | Package | Version | Source |
|-------|---------|---------|--------|
| Web Framework | Django | 5.2.19 | `requirements.txt` line 4 |
| Python | — | 3.12 | `Dockerfile` line 1, AGENTS.md |
| Config | django-environ | >=0.11,<1.0 | `requirements.txt` |
| Static files | whitenoise | >=6.6,<7.0 | `requirements.txt` |
| WSGI Server | gunicorn | >=21.0 | `requirements.txt` |
| Database driver | psycopg[binary] | >=3.1 | `requirements.txt` (PostgreSQL optional) |
| Password hashing | bcrypt | 4.2.1 | `requirements.txt` |
| Background jobs | django-q2 | 1.11.1 | `requirements.txt` |
| Image processing | Pillow | >=10.0 | `requirements.txt` |
| PDF generation | reportlab | >=4.0,<6.0 | `requirements.txt` |
| QR codes | qrcode | >=8.0,<9.0 | `requirements.txt` |
| PDF reading (tests) | pypdf | >=5.0,<8.0 | `requirements.txt` |
| AI chatbot | google-genai | >=1.0 | `requirements.txt` |
| WhatsApp/SMS | twilio | >=9.0 | `requirements.txt` |
| Phone numbers | phonenumbers | >=8.13 | `requirements.txt` |
| Error tracking | sentry-sdk | >=2.76,<3.0 | `requirements.txt` (optional, only if SENTRY_DSN set) |
| Env loader | python-dotenv | >=1.0 | `requirements.txt` |
| HTTP client | requests | >=2.31 | `requirements.txt` |
| Data import | pandas | >=2.0 | `requirements.txt` |
| Excel import | openpyxl | >=3.1 | `requirements.txt` |
| Reverse proxy | Caddy | — | `deploy/Caddyfile` |
| Container | Docker | — | `Dockerfile`, `docker-compose.yml` |
| DB (dev) | SQLite | built-in | `settings.py` default |
| DB (prod) | PostgreSQL | 16 (image) | `docker-compose.yml` line 24 |
| Translations | Django i18n | built-in | `settings.py` LANGUAGES = [en, hi] |

**Verify nahi hua:** requirements-dev.txt ka exact content (CI refer karta hai lekin file read nahi ki gayi is audit mein).


---

## 4. Data Models (students/models.py)

Sabhi models ek hi database mein hain (per-college deployment). Koi college-wise foreign key nahi hai kyunki har college ka alag DB hai.

### Model-wise details

| Model | Kaam | Important Fields | Relations |
|-------|------|------------------|-----------|
| `StudentProfile` | Student record + login profile | `user` (OneToOne), `name`, `registration_number` (unique), `phone`, `email`, `branch`, `semester`, `photo`, `is_password_changed`, `consent_given_at`, `dashboard_seen_at` | `user` → Django User |
| `Subject` | Subject taught in a branch/semester | `branch`, `semester`, `subject_code`, `subject_name`, `credits`, `is_active` | unique_together (branch, semester, subject_code) |
| `InternalExam` | Internal marks (CA/MSE/Assignment/Attendance) | `student`, `subject`, `exam_type`, `marks_obtained`, `max_marks`, `exam_date` | FK StudentProfile, FK Subject |
| `SemesterResult` | Published semester results | `student`, `semester`, `subject`, `internal_marks`, `external_marks`, `total_marks`, `grade`, `is_pass` | FK StudentProfile, FK Subject |
| `Attendance` | Daily attendance | `student`, `subject`, `date`, `is_present`, `marked_by` | FK StudentProfile, FK Subject |
| `FacultyProfile` | Teacher profile + subject assignments | `user`, `name`, `email`, `phone`, `department`, `designation`, `subjects` (M2M), `can_send_notices`, `can_enter_marks`, `can_upload_materials` | FK User, M2M Subject |
| `Assignment` | Teacher-uploaded assignments | `title`, `subject`, `assigned_by`, `due_date`, `attachment`, `is_active` | FK Subject, FK FacultyProfile |
| `StudyMaterial` | Notes/PDFs/links | `title`, `subject`, `uploaded_by`, `material_type`, `file`, `external_link` | FK Subject, FK FacultyProfile |
| `ClassSchedule` | Timetable slots | `subject`, `faculty`, `weekday`, `start_time`, `end_time`, `room`, `is_active` | FK Subject, FK FacultyProfile |
| `Notice` | College/class notices | `title`, `content`, `created_by`, `target_branches`, `target_semesters`, `is_active` | FK FacultyProfile |
| `CSVUpload` | Bulk import tracking | `file`, `upload_type`, `uploaded_by`, `is_processed`, `records_created`, `records_updated`, `errors` | — |
| `BannerImage` | Dashboard banner images | `title`, `image`, `uploaded_by`, `is_active` | FK User |
| `Doubt` | Student doubt forum | `student`, `title`, `content`, `is_resolved` | FK StudentProfile |
| `DoubtReply` | Replies to doubts | `doubt`, `user`, `content` | FK Doubt, FK User |
| `FeeStructure` | Fee definitions per branch/semester | `branch`, `semester`, `fee_type`, `amount`, `academic_year`, `due_date`, `is_active` | — |
| `FeePayment` | Fee payments recorded | `student`, `fee_structure`, `amount_paid`, `payment_date`, `receipt_number` (unique), `payment_mode`, `status` | FK StudentProfile, FK FeeStructure |
| `ExamSchedule` | Exam date sheet | `branch`, `semester`, `subject`, `exam_type`, `exam_date`, `start_time`, `end_time`, `room`, `is_active` | FK Subject |
| `LeaveApplication` | Student leave requests | `student`, `leave_type`, `from_date`, `to_date`, `reason`, `status`, `reviewed_by`, `admin_remarks` | FK StudentProfile, FK User |
| `Feedback` | Student feedback on subjects/faculty | `student`, `subject`, `faculty`, `rating` (1-5), `comments`, `semester` | FK StudentProfile, FK Subject, FK FacultyProfile |
| `Event` | College calendar events | `title`, `description`, `event_date`, `event_type`, `venue`, `is_active`, `created_by` | FK User |
| `WebsiteVisit` | Page visit analytics | `path`, `user`, `session_key`, `ip_address`, `user_agent`, `duration_seconds` | FK User |
| `AuditLog` | Who changed what | `user`, `action`, `model_name`, `object_id`, `detail`, `ip_address` | FK User |
| `BugReport` | In-app bug/feedback reports | `user`, `role`, `category`, `message`, `page_url`, `status` | FK User |
| `GuardianProfile` | Parent/guardian read-only access | `user`, `name`, `phone`, `email`, `students` (M2M), `relationship`, `is_active` | FK User, M2M StudentProfile |
| `ErrorEvent` | Server errors stored in DB | `level`, `logger_name`, `message`, `path`, `fingerprint` (unique), `count`, `is_resolved` | — |
| `BackupRecord` | Backup history | `path`, `kind`, `size_bytes`, `encrypted`, `checksum`, `created_at` | — |
| `DashboardSettings` | Per-college dashboard toggles (singleton) | `hidden_cards` (JSON), `quick_links` (JSON), `show_dark_mode_toggle` | — |
| `ExamDocument` | Hall ticket/marksheet audit + verification | `kind`, `student`, `semester`, `exam_type`, `verification_code` (unique), `issued_by`, `downloads`, `is_valid` | FK StudentProfile, FK User |

### platform_admin/models.py

| Model | Kaam |
|-------|------|
| `Plan` | Subscription plans with feature flags (module codes) |
| `College` | College registration (slug, domain, plan, status, subscription dates) |
| `UsageSnapshot` | Per-day usage metrics reported by college deployments |
| `SupportTicket` | Platform-level support tickets from colleges |
| `TicketReply` | Replies to support tickets |
| `DemoRequest` | Public landing page demo requests |

Verify status: **All models read from students/models.py** — field names, choices, relations confirmed from source.


---

## 5. Role-wise Features

### Student

| Feature | URL/Page | Verify Status |
|---------|----------|---------------|
| Login / Logout | `/login/`, `/logout/` | Verified (views_student.py) |
| Set password (one-time link) | `/set-password/<uidb64>/<token>/` | Verified |
| Change password | `/change-password/` | Verified |
| Dashboard (attendance, fees, notices, events, results summary) | `/dashboard/` | Verified |
| View own attendance | `/attendance/` | Verified |
| View own results (SGPA/CGPA) | `/results/` | Verified |
| View timetable | `/timetable/` | Verified |
| View notices (filtered by branch/semester) | `/notices/` | Verified |
| View study materials & assignments | `/materials/` | Verified |
| View exam schedule | `/exam-schedule/` | Verified |
| Download hall ticket / marksheet (PDF) | `/exam/hall-ticket/`, `/exam/marksheet/` | Verified |
| Verify document publicly | `/verify/<code>/` | Verified |
| Apply for leave | `/leave-apply/` | Verified |
| Submit feedback | `/feedback/` | Verified |
| View events | `/events/` | Verified |
| Certificate request (UI only, browser print) | `/certificates/` | Verified (UI) |
| Edit own profile | `/profile/edit/` | Verified |
| Report a problem | `/report-problem/` | Verified |
| WhatsApp set-password link (from model method) | `get_whatsapp_url()` | Verified (model method, not a page) |

### Teacher (Faculty)

| Feature | URL/Page | Verify Status |
|---------|----------|---------------|
| Dashboard (own classes, at-risk students) | `/teacher/` | Verified |
| View own students (with attendance %) | `/teacher/students/` | Verified |
| Take attendance (bulk) | `/teacher/attendance/` | Verified |
| Enter marks (spreadsheet style) | `/teacher/marks/` | Verified |
| Upload assignments | `/teacher/assignments/` | Verified |
| Upload study materials | `/teacher/materials/` | Verified |
| Manage class schedule | `/teacher/schedule/` | Verified |
| Create/edit/delete notices (own classes only) | `/teacher/notices/` | Verified |
| Generate exam documents (own classes) | `/admin-panel/exam-documents/` | Verified (restricted by teacher_classes) |

### Admin (Office Staff)

| Feature | URL/Page | Verify Status |
|---------|----------|---------------|
| Admin dashboard (aggregate stats) | `/admin-panel/` | Verified |
| Manage students (CRUD, export, anonymize, data export) | `/admin-panel/students/` | Verified |
| Manage teachers (CRUD) | `/admin-panel/teachers/` | Verified |
| Manage admins (CRUD, no accidental superuser) | `/admin-panel/admins/` | Verified |
| CSV bulk import (students, subjects, marks, results, attendance, notices) | `/admin-panel/upload/` | Verified |
| Manage subjects | `/admin-panel/subjects/` | Verified |
| Enter marks | `/admin-panel/marks/` | Verified |
| Take attendance (bulk) | `/admin-panel/take-attendance/` | Verified |
| Manage fee structure & record payments | `/admin-panel/fees/` | Verified |
| Manage exam schedule | `/admin-panel/exam-schedule/` | Verified |
| Manage notices | `/admin-panel/notices/` | Verified |
| Manage events | `/admin-panel/events/` | Verified |
| Review leave applications | `/admin-panel/leave-applications/` | Verified |
| View feedback reports | `/admin-panel/feedback/` | Verified |
| Upload banners | `/banners/` | Verified |
| View system status | `/admin-panel/system-status/` | Verified |
| View bug reports | `/admin-panel/bug-reports/` | Verified |
| Export set-password links CSV | `/admin-panel/credentials/export-links/` | Verified |

### Parent / Guardian

| Feature | URL/Page | Verify Status |
|---------|----------|---------------|
| Login (via office-issued link) | `/login/` | Verified |
| Dashboard (children's attendance %, fees, notices) | `/parent/` | Verified |
| View individual child details | `/parent/child/<pk>/` | Verified |
| Scope: only own children (guessed ID → 404) | — | Verified (_owned_child) |
| Self-service parent registration | — | **Missing** (BACKLOG.md item 15) |

### Super Admin / Platform Admin

| Feature | URL/Page | Verify Status |
|---------|----------|---------------|
| Platform overview (colleges stats) | `/platform/` | Verified |
| Manage colleges (CRUD, suspend/resume) | `/platform/colleges/` | Verified |
| Manage plans (pricing, features) | `/platform/plans/` | Verified |
| View usage report | `/platform/usage/` | Verified |
| Manage support tickets | `/platform/tickets/` | Verified |
| College metrics endpoint (token-authenticated) | `/platform/metrics/<slug>/` | Verified |
| Access restricted to superusers + "Platform Admin" group | `platform_admin_required` | Verified |


---

## 6. Features ka Asli Status (Table)

| Feature | Status | Saboot (File/Test) |
|---------|--------|-------------------|
| Student login + lockout | Poora kaam karta hai | `students/views_student.py:student_login`, `students/security.py`, `students/tests/test_auth_permissions.py` |
| Set-password link (no plaintext password) | Poora kaam karta hai | `students/password_links.py`, `students/views_student.py:set_password` |
| Student dashboard | Poora kaam karta hai | `students/views/dashboard_data.py:build`, `students/views_student.py:student_dashboard` |
| Attendance (student view + teacher marking) | Poora kaam karta hai | `students/views/student_pages.py:student_attendance`, `students/views/teacher.py:teacher_take_attendance` |
| Marks entry & results | Poora kaam karta hai | `students/views/academics.py:marks_entry`, `students/views/student_pages.py:student_results` |
| Fee structure & payment recording | Poora kaam karta hai | `students/views/finance.py:*` |
| CSV bulk import | Poora kaam karta hai | `students/views/imports.py:csv_upload`, `students/upload_router.py` |
| Exam documents (hall ticket/marksheet PDF + verify) | Poora kaam karta hai | `students/views/exams.py:*`, `students/pdf.py`, `students/exams.py` |
| Notice board (admin + teacher) | Poora kaam karta hai | `students/views/content.py:*` |
| Study materials & assignments | Poora kaam karta hai | `students/views/teacher.py:teacher_materials, teacher_assignments` |
| Timetable (class schedule) | Poora kaam karta hai | `students/views/student_pages.py:student_timetable`, `students/views/teacher.py:teacher_schedule` |
| Leave application + review | Poora kaam karta hai | `students/views_student.py:student_leave_apply`, `students/views/leave_feedback.py:*` |
| Student feedback | Poora kaam karta hai | `students/views_student.py:student_feedback`, `students/views/leave_feedback.py:feedback_report` |
| Events calendar | Poora kaam karta hai | `students/views/content.py:event_list`, `students/views_student.py:student_events` |
| Doubt forum | Poora kaam karta hai | `students/views/content.py:doubt_list, doubt_detail` |
| AI chatbot (Gemini + offline fallback) | Poora kaam karta hai (fallback mojood) | `students/views/content.py:ai_chatbot_api`, `students/ai_helper.py` |
| Parent portal (read-only) | Poora kaam karta hai (office-linked only) | `students/views/parents.py:*`, `students/models.py:GuardianProfile` |
| Media file protection (login required) | Poora kaam karta hai | `students/views/media.py:serve_media`, `college_ums/urls.py` |
| Audit log | Poora kaam karta hai | `students/audit.py:log_action`, `students/models.py:AuditLog` |
| Error tracking in DB | Poora kaam karta hai | `students/error_tracking.py:DatabaseErrorHandler`, `students/models.py:ErrorEvent` |
| System status page | Poora kaam karta hai | `students/views/system_status.py:system_status` |
| Bug report system | Poora kaam karta hai | `students/views/reports_feedback.py:*`, `students/models.py:BugReport` |
| Background jobs (django-q2) | Poora kaam karta hai | `students/tasks.py:*` |
| Login brute-force protection | Poora kaam karta hai | `students/security.py:*` |
| Upload validation (extension + size) | Poora kaam karta hai | `students/security.py:validate_upload`, `students/forms.py:CSVUploadForm` |
| Multi-college isolation (separate deployments) | Poora kaam karta hai | `college_ums/settings.py` (single DB), `students/tests/test_isolation.py` |
| PWA (service worker, manifest, offline) | Poora kaam karta hai | `students/views/common.py:service_worker, manifest, offline`, `templates/sw.js` |
| Hindi/English i18n | Poora kaam karta hai | `college_ums/settings.py:LANGUAGES`, `locale/hi/` |
| Razorpay / online fee payment | **Missing** | `dashboard_data.py:fees` checks `RAZORPAY_KEY_ID` but no payment views exist (verify nahi hua — no Razorpay code in views) |
| Parent self-service registration | **Missing** | BACKLOG.md item 15 |
| Timetable clash detection | **Missing** | BACKLOG.md |
| Notification bell (real-time) | **Missing** | BACKLOG.md |
| Global search | **Missing** | BACKLOG.md |
| Server-side PDF certificates | **Placeholder-UI only** | `templates/student/certificates.html` (browser print only, per BACKLOG item 12) |
| Sentry integration | Placeholder (optional, needs DSN) | `college_ums/settings.py` lines 394-421 |
| Twilio WhatsApp/SMS | Placeholder (needs credentials) | `students/tasks.py:send_whatsapp_task, send_sms_task` — credentials empty in `.env` |
| Email (SMTP) | Placeholder (needs credentials) | `students/tasks.py:send_email_task` — `EMAIL_HOST_USER` empty in `.env` |


---

## 7. Security

### Kya laga hai (verify kiya gaya code se)

| Security Measure | Implementation | File |
|-----------------|---------------|------|
| SECRET_KEY mandatory (no insecure fallback) | Raises `ImproperlyConfigured` if missing or weak | `college_ums/settings.py` lines 14-46 |
| Login brute-force lockout | Per username+IP, cache-backed, 5 attempts default, 15 min lockout | `students/security.py`, `students/views_student.py:student_login` |
| CSP + Permissions-Policy headers | `SecurityHeadersMiddleware` adds CSP, Permissions-Policy, COOP, X-Content-Type-Options, X-Frame-Options | `students/middleware.py:SecurityHeadersMiddleware` |
| Secure cookies in production | `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SAMESITE=Lax` | `college_ums/settings.py` lines 432-436 |
| HSTS (production/staging) | `SECURE_HSTS_SECONDS`, include subdomains, preload (prod only) | `college_ums/settings.py` lines 439-442 |
| Media file protection | `/media/` served via Django with login check; `csv_uploads/` staff-only; path traversal blocked | `students/views/media.py`, `college_ums/urls.py` |
| Upload validation | Extension allow-list, blocked dangerous extensions, size limits, filename sanitization | `students/security.py:validate_upload`, `students/forms.py:CSVUploadForm` |
| Password reset tokens | Django `PasswordResetTokenGenerator`, 48h expiry, one-time | `students/password_links.py` |
| Audit log | `log_action()` wraps every mutation; never breaks request | `students/audit.py` |
| PII redaction in logs/Sentry | `redact_text()`, `redact_mapping()`, `scrub_sentry_event()` | `students/privacy.py` |
| Role-based access control | `@admin_required`, `@teacher_required`, `@login_required`, object-level checks | `students/views/common.py`, `students/views/exams.py:can_view_document` |
| Guardian data isolation | `_owned_child()` filters by guardian's own students relation | `students/views/parents.py` |
| CSRF protection | `CsrfViewMiddleware`, `CSRF_TRUSTED_ORIGINS` env-driven | `college_ums/settings.py` |
| SQL injection protection | Django ORM everywhere (parameterized queries) | Confirmed across all views |
| X-Forwarded-For trust gated | Only when `TRUST_PROXY_HEADERS=True` | `students/security.py:client_ip` |
| Sentry PII scrubbing | `data_collection` disables user_info, cookies, request_body, query_string | `college_ums/settings.py` lines 410-421 |

### Kya kamzor hai (weaknesses)

| Weakness | Detail | File |
|----------|--------|------|
| CSP allows `'unsafe-inline'` | Inline styles/scripts still used; middleware notes this | `students/middleware.py` lines 67-68 |
| Login lockout uses locmem cache | Counter resets on server restart; no Redis | `college_ums/settings.py` — no `CACHES` key found |
| No Redis for caching/sessions | `CACHES` not explicitly configured | `college_ums/settings.py` — no `CACHES` key found |
| `'unsafe-inline'` in script-src | CSP permits inline scripts | `college_ums/settings.py:SECURITY_CSP` |
| AI chat context includes username/role | Sent to Gemini (if configured) | `students/views/content.py:ai_chatbot_api` lines 221-230 |
| No 2FA/MFA | Not implemented anywhere | No MFA code found |
| Rate limiting only on AI chat + bug reports | No global rate limiting on other endpoints | `students/security.py:rate_limit_hit` used only in 2 places |


---

## 8. Integrations

| Integration | Asli State | Keys Chahiye? | Abhi Kaam Karta Hai? | File |
|-------------|-----------|---------------|---------------------|------|
| Email (SMTP) | Backend configured but credentials empty in `.env` | `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | No (console backend in DEBUG, SMTP in prod but no creds) | `students/tasks.py:send_email_task`, `college_ums/settings.py` |
| WhatsApp (Twilio) | Code ready, credentials empty in `.env` | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | No (skipped if no credentials) | `students/tasks.py:send_whatsapp_task` |
| SMS (Twilio) | Code ready, `TWILIO_SMS_FROM` empty | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SMS_FROM` | No | `students/tasks.py:send_sms_task` |
| AI Chatbot (Google Gemini) | Code ready, `GEMINI_API_KEY` present in `.env` | `GEMINI_API_KEY` | Yes (key present), but has offline fallback | `students/ai_helper.py`, `.env` line 14 |
| Sentry | Code ready, `SENTRY_DSN` empty | `SENTRY_DSN` | No (disabled by default) | `college_ums/settings.py` lines 394-421 |
| Razorpay / Online Payment | **Missing** — no code | `RAZORPAY_KEY_ID` (referenced but not implemented) | No | `students/dashboard_data.py:fees` checks `gateway_configured` but no payment views |
| PostgreSQL | Supported (optional) | `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Yes (if configured) | `college_ums/settings.py:DB_ENGINE` aliases |

Verify nahi hua: Twilio SMS actually delivers (needs real credentials and phone numbers). Email actually delivers (needs SMTP creds). Gemini API actually responds (key present in `.env` but not tested in this audit).

---

## 9. Background Jobs, Backups, Monitoring, Management Commands

### Background Jobs (django-q2, ORM broker — no Redis)

| Task | Kaam | Trigger | File |
|------|------|---------|------|
| `send_email_task` | Send one email | `notify('email', ...)` | `students/tasks.py:send_email_task` |
| `send_whatsapp_task` | Send WhatsApp via Twilio | `notify('whatsapp', ...)` | `students/tasks.py:send_whatsapp_task` |
| `send_sms_task` | Send SMS via Twilio | `notify('sms', ...)` | `students/tasks.py:send_sms_task` |
| `send_credentials_task` | WhatsApp set-password link to student | After CSV import / student create | `students/tasks.py:send_credentials_task` |
| `notify()` | Dispatch to right channel | Views call this | `students/tasks.py:notify` |
| `with_retries()` | Exponential backoff for flaky calls | Internal helper | `students/tasks.py:with_retries` |
| `enqueue()` | Queue or run inline if broker down | All task callers | `students/tasks.py:enqueue` |

Q_CLUSTER config: workers=2, timeout=120s, retry=180s, max_attempts=3, ORM broker, sync=False (default).

### Management Commands (verify nahi hua — commands directory not found in read files)

From code references:
- `manage.py create_college` — multi-college onboarding (mentioned in VERIFICATION.md item 13)
- `manage.py send_error_digest` — emails super admin (mentioned in CHANGELOG.md)
- `manage.py diagnose_college <domain>` — 13 health checks (mentioned in CHANGELOG.md)
- `manage.py record_backup` — backup bookkeeping (mentioned in CHANGELOG.md)
- `manage.py seed_demo` — demo data (mentioned in CHANGELOG.md)
- `manage.py add_guardian` — parent portal setup (mentioned in CHANGELOG.md)
- `manage.py check_email` — email dry-run (mentioned in .env.example)
- `compile_translations` — Django translation compile (entrypoint.sh)
- `collectstatic` — static files (entrypoint.sh)

Verify nahi hua: actual `management/commands/` directory not listed in file scan — commands may be in a location not captured or the VERIFICATION.md/CHANGELOG.md claims need code verification.

### Backups

| Item | Detail | File |
|------|--------|------|
| `scripts/backup_db.sh` | pg_dump/gzip, retention, encrypted, empty-dump fail | VERIFICATION.md item 15 |
| `BACKUP_DIR` | Configurable via env (default: `backups/` under BASE_DIR) | `college_ums/settings.py:391` |
| `BACKUP_MAX_AGE_HOURS` | Staleness threshold (default 48) | `college_ums/settings.py:392` |
| `BackupRecord` model | Tracks what backup script wrote | `students/models.py:BackupRecord` |
| `manage.py record_backup` | Bookkeeping (claimed in CHANGELOG) | verify nahi hua |

### Monitoring

| Item | Detail | File |
|------|--------|------|
| `/healthz/` | Liveness probe (DB-free) | `students/views/common.py:healthz` |
| `/readyz/` | Readiness probe (DB + cache) | `students/views/common.py:readyz` |
| `/admin-panel/system-status/` | Full system health page | `students/views/system_status.py:system_status` |
| Sentry | Optional error tracking (PII scrubbed) | `college_ums/settings.py` |
| `ErrorEvent` model | DB-stored ERROR/CRITICAL logs | `students/models.py:ErrorEvent` |
| `send_error_digest` | Daily error email to super admin | claimed in CHANGELOG.md |

### Cron / Scheduling (verify nahi hua)

VERIFICATION.md mentions cron line for backups but actual cron configuration not found in code scan.


---

## 10. Deployment

### Deploy Stack Files

| File | Kaam |
|------|------|
| `Dockerfile` | Python 3.12-slim, gunicorn, unprivileged user, HEALTHCHECK |
| `docker-compose.yml` | Dev stack: Django + Postgres 16 |
| `docker-compose.prod.yml` | Prod stack (verify nahi hua — file exists but not read) |
| `deploy/Caddyfile` | Reverse proxy, TLS, security headers, no direct /media/ serving |
| `entrypoint.sh` | Fail fast → compile translations → migrate → collectstatic → gunicorn |
| `scripts/provision_server.sh` | New server deployment (claimed in CHANGELOG) |
| `scripts/new_college.sh` | Add new college (claimed in VERIFICATION.md) |
| `scripts/deploy.sh` | Backup → build → migrate → health check → rollback (claimed in CHANGELOG) |
| `scripts/update_all.sh` | Update all colleges at once (claimed in CHANGELOG) |
| `scripts/backup_db.sh` | Encrypted database backup |

### Naya College kaise add hota hai

1. Clone repo on new server
2. Copy `.env.example` to `.env`, fill in per-college values
3. Set `COLLEGE_SLUG`, `COLLEGE_NAME`, `DOMAIN`, `SECRET_KEY`, `ALLOWED_HOSTS`
4. Run `python manage.py create_college` (claimed) or `scripts/new_college.sh`
5. Run `python manage.py migrate`
6. Run `python manage.py collectstatic`
7. Start gunicorn behind Caddy

Verify nahi hua: `scripts/new_college.sh` and `manage.py create_college` not found in file scan — claims from VERIFICATION.md/CHANGELOG.md only.

### Environment Variables (naam aur kaam, values nahi)

| Variable | Kaam |
|----------|------|
| `SECRET_KEY` | Django secret key (mandatory, no fallback) |
| `DEBUG` | True/False — development vs production |
| `ENVIRONMENT` | development \| staging \| production |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF |
| `COLLEGE_NAME` | College display name |
| `COLLEGE_LOGO` | Logo static path or URL |
| `PRIMARY_COLOR` | Brand color (hex) |
| `COLLEGE_EMAIL` | College contact email |
| `COLLEGE_PHONE` | College phone |
| `COLLEGE_ADDRESS` | College address |
| `COLLEGE_WEBSITE` | College website |
| `COLLEGE_AFFILIATION` | Affiliation board |
| `COLLEGE_ESTABLISHED` | Year established |
| `COLLEGE_PRINCIPAL_NAME` | Principal name |
| `PORTAL_URL` | Portal URL (for password links) |
| `TWILIO_ACCOUNT_SID` | Twilio credentials |
| `TWILIO_AUTH_TOKEN` | Twilio credentials |
| `TWILIO_WHATSAPP_FROM` | WhatsApp sender |
| `TWILIO_SMS_FROM` | SMS sender |
| `GEMINI_API_KEY` | Google Gemini AI key |
| `EMAIL_BACKEND` | Django email backend |
| `EMAIL_HOST` / `EMAIL_PORT` | SMTP server |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP credentials |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL` | SMTP security |
| `DEFAULT_FROM_EMAIL` | From address |
| `DB_ENGINE` | Database backend (sqlite3/postgresql/mysql) |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | Database connection |
| `COLLEGE_SLUG` | College identifier for platform middleware |
| `PLATFORM_ADMIN_GROUP` | Group name for platform admin access |
| `PLATFORM_METRICS_TOKEN` | Shared metrics token |
| `PLATFORM_BACKUP_DIR` | Backup directory on platform host |
| `SENTRY_DSN` | Sentry error tracking DSN (optional) |
| `SENTRY_ENV` | Sentry environment tag |
| `BACKUP_DIR` | Local backup directory |
| `BACKUP_MAX_AGE_HOURS` | Backup staleness threshold |
| `CSV_MAX_UPLOAD_MB` | Max CSV file size |
| `PASSWORD_TOKEN_TIMEOUT_HOURS` | Password reset link expiry |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCKOUT_MINUTES` | Brute-force protection |
| `TRUST_PROXY_HEADERS` | Trust X-Forwarded-For (behind Caddy) |
| `SECURITY_CSP` | Content Security Policy value |
| `MEDIA_PROTECTED` | Serve media via Django login check |
| `LANDING_PAGE_ENABLED` | Show public landing page |
| `MATERIAL_SHARED_FOLDER_URL` | External shared folder link |
| `Q_WORKERS` / `Q_TIMEOUT` / `Q_RETRY` / `Q_MAX_ATTEMPTS` | django-q2 config |
| `TASK_MAX_ATTEMPTS` | Per-task retry attempts |
| `LOG_FORMAT` / `LOG_LEVEL` | Logging configuration |
| `PRIVACY_LAST_UPDATED` / `DATA_RETENTION_YEARS` / `AUDIT_LOG_RETENTION_DAYS` | Privacy/retention |


---

## 11. Testing

| Item | Detail |
|------|--------|
| Test files | 34 test files in `students/tests/` |
| Test count claimed | VERIFICATION.md says "78 tests OK" (verify nahi hua — test run not executed in this audit) |
| Test categories | Auth/permissions, CSV upload, dashboard redesign, demo & feedback, Docker context, exam documents, i18n/a11y, isolation, logout, marks grid, notifications (real), observability, ops, ops status, pagination, parents, password links, performance, privacy, PWA, security, settings, smoke pages, student pages, tasks, teacher panel, UX |
| Key test files | `test_isolation.py` — multi-college data isolation; `test_security.py` — permission matrix (40+ URLs × 4 roles); `test_csv_upload.py` — upload validation; `test_password_links.py` — set-password flow |
| CI (GitHub Actions) | `.github/workflows/ci.yml` — runs on push/PR: tests, migrations check (`makemigrations --check --dry-run`), ruff lint, bandit security, pip-audit, prod-settings smoke (`DEBUG=False`) |
| CI Python version | 3.12 |
| CI steps | Install deps → `manage.py check` → `compile_translations --check` → `collectstatic` → `manage.py test` |

**What is NOT covered by tests (verify nahi hua):**
- Docker/Caddy runtime validation (docker not installed on this machine per VERIFICATION.md)
- Postgres backup/restore (pg_dump absent on this machine)
- Razorpay payment flow (no code)
- Parent self-service registration (no code)
- Real email/SMS/WhatsApp delivery (no credentials in test env)

---

## 12. Code Health

### Sabse bade / complex files

| File | Lines (approx) | Kaam |
|------|---------------|------|
| `students/models.py` | ~880 | All 25+ models |
| `students/views/exams.py` | ~260 | Exam documents (hall ticket, marksheet, bulk, verify) |
| `students/views/teacher.py` | ~370 | Teacher panel (attendance, marks, notices, materials, schedule) |
| `students/views/people.py` | ~350 | Student/teacher/admin CRUD + exports |
| `students/views/dashboard.py` | ~140 | Admin + teacher dashboards + reports |
| `students/dashboard_data.py` | ~330 | Student dashboard data aggregation |
| `students/pdf.py` | ~340 | ReportLab PDF generation (hall ticket + marksheet) |
| `college_ums/settings.py` | ~490 | All settings, env-driven |
| `students/ai_helper.py` | ~68 | AI chatbot with Gemini + fallback |
| `students/privacy.py` | ~130 | PII redaction for logs/Sentry |

### Duplicate / Dead Code

- `students/views_student.py` has `student_dashboard`, `student_fees`, `student_exam_schedule`, etc. — also `students/views/student_pages.py` has overlapping student pages (`student_attendance`, `student_results`, etc.). Some overlap but different purposes (dashboard aggregate vs individual pages).
- `students/views/common.py` has `is_admin`, `is_teacher` — also `students/views/academics.py` imports and re-uses them.
- `students/views/__init__.py` re-exports 79 names from 17 sub-modules — keeps `from . import views` working.

### TODO / FIXME / Technical Debt

From `BACKLOG.md` (open items):
1. Logout is GET (CSRF logout risk) — `students/views_student.py:student_logout` — **open**
2. Cache/sessions are locmem/db — lockout counter resets on restart — **open**
3. Feature flags (`College.has_feature()`) stored but not used to hide menu items — **open**
4. Study material not scoped per branch/semester — **open**
5. ~25 inline `style="..."` attributes remain — **open**
6. Django admin unthemed — **open**
7. Junk staff accounts in dev DB — **open**
8. Certificate/PDF generation is browser-print only — **open**
9. No automated visual regression — **open**
10. Landing page screenshots are CSS placeholders — **open**
11. Parent portal is office-linked only, no self-service — **open**

From `VERIFICATION.md` (still open):
- Docker/Caddy runtime validation
- Django 5.2 upgrade (already done per CHANGELOG, was 4.2)
- Postgres backup/restore not verified on this machine


---

## 13. Known Problems (Top 10 Risks/Bugs)

| # | Risk/Bug | Severity | Evidence |
|---|----------|----------|----------|
| 1 | Logout via GET link — any `` tag can log out a user | 🔴 High | `students/views_student.py:student_logout` (GET renders confirm, POST logs out — partially fixed but GET still exists for confirmation) |
| 2 | Login lockout uses locmem cache — resets on restart, no distributed rate limiting | 🟠 Medium | `students/security.py` uses `django.core.cache.cache` (backend not configured in settings.py — verify nahi hua) |
| 3 | No Redis — caching and sessions may be database-backed (slow under load) | 🟠 Medium | `college_ums/settings.py` — no `CACHES` key found |
| 4 | CSP allows `'unsafe-inline'` — XSS risk if any user input is reflected in inline contexts | 🟠 Medium | `college_ums/settings.py:SECURITY_CSP` |
| 5 | Razorpay/payment missing — fee status shows "pay_online" but no payment flow | 🟡 Low | `students/dashboard_data.py:fees` line 213 checks `RAZORPAY_KEY_ID` but no payment views exist |
| 6 | Parent portal is office-linked only — no self-service parent registration | 🟡 Low | BACKLOG.md item 15 |
| 7 | No 2FA/MFA anywhere | 🟡 Low | No MFA code found in codebase |
| 8 | Twilio/Email credentials empty in `.env` — notifications silently skipped | 🟡 Low | `.env` lines 6-8, 135-138 |
| 9 | Postgres backup/restore not verified on this machine | 🟡 Low | VERIFICATION.md item 53 |
| 10 | Docker/Caddy not validated (docker not installed on audit machine) | 🟡 Low | VERIFICATION.md item 15 |

---

## 14. Jo Kaam Abhi Baaki Hai (Agla Sahi Order)

| Priority | Kaam | Reason | File/Location |
|----------|------|--------|---------------|
| 1 | Fix logout GET → POST only | CSRF/security risk | `students/views_student.py:student_logout`, `templates/base.html` |
| 2 | Configure Redis for cache/sessions | Distributed lockout, performance | `college_ums/settings.py` — add `CACHES` |
| 3 | Implement Razorpay/UPI fee payment | `pay_online` flag is fake | No code exists — new feature |
| 4 | Parent self-service registration | Currently office-only | `students/views/parents.py` — new views needed |
| 5 | Timetable clash detection | Teacher schedule validation | `students/models.py:ClassSchedule` — new logic |
| 6 | Server-side PDF certificates | Currently browser-print only | `templates/student/certificates.html` |
| 7 | Global search | Cross-model search | New feature |
| 8 | Notification bell (real-time) | Currently no bell UI | New feature |
| 9 | Visual regression testing | No headless browser tests | CI addition |
| 10 | Verify Postgres backup/restore | Production readiness | `scripts/backup_db.sh` |

---

## 15. Mere Liye Ek Page (Principal Ke Liye, 10 Line, Non-Technical)

**College UMS kya hai aur kya kar sakta hai:**

Yeh ek college management system hai jisse aapke college ke students, teachers aur admin staff ek hi portal par apna kaam manage kar sakte hain. Students apni attendance, marks, fees, timetable aur exam hall ticket/marksheet download kar sakte hain. Teachers apni class ki attendance mark kar sakte hain, marks daal sakte hain, aur notices bhej sakte hain. Admin office staff students aur teachers ka hisaab rakhta hai, fees collect karta hai, aur bulk CSV import karke data upload karta hai. Parents apne bacchon ki attendance aur fees dekh sakte hain (office ke dwara link milne par). Sab data surakshit hai — login chahiye, file uploads protected hain, aur audit log har change ka record rakhta hai.

**Abhi jo nahi hai:**
- Online fee payment (Razorpay/UPI) abhi nahi hai — fees abhi office mein cash/cheque se jama karne padenge.
- Parents khud se register nahi kar sakte — office unhe link bhejti hai.
- AI chatbot ke liye alag API key chahiye hai, abhi yeh offline mode mein kaam karta hai.
- WhatsApp aur SMS notifications ke liye Twilio account chahiye hai, abhi setup bina nahi chalenge.

Agar aap chahte hain ki college ka poora record digital aur surakshit rahe, toh yeh system taiyaar hai. Kuch advanced features (online payment, parent self-registration) agle version mein add kiye ja sakte hain.

---

*Yeh PROJECT_SUMMARY.md asli source code se generate kiya gaya hai. Koi andaaza nahi lagaya gaya. Jo verify nahi ho saka uske saath "verify nahi hua" likha gaya hai.*

