# College UMS — Project Report

## 1. Overview
A Django-based **College University Management System (UMS)** for managing students, faculty, attendance, marks, results, fees, notices, events, leave, feedback, and a doubt forum. Includes CSV bulk import/export, an AI chatbot endpoint, and a teacher panel.

- **Framework:** Django 4.2.29 (Python 3.12+)
- **App:** single Django app `students`
- **DB:** SQLite by default (PostgreSQL optional via env)
- **Deployment targets:** Render (render.yaml), Docker, gunicorn
- **Time zone:** Asia/Kolkata

## 2. Tech Stack
- Django 4.2, WhiteNoise, django-environ, python-dotenv
- pandas, openpyxl (CSV/Excel import/export)
- Pillow (images/banners)
- requests, google-genai, twilio, phonenumbers (optional integrations)
- gunicorn, psycopg (production/Postgres)

## 3. Project Structure
```
scratch/
├── manage.py
├── college_ums/        # project package (settings, urls, wsgi, asgi)
├── students/           # main app
│   ├── models.py       # all domain models
│   ├── views.py        # admin + teacher views
│   ├── views_student.py # student-facing views
│   ├── forms.py, urls.py, admin.py
│   ├── csv_processor.py, data_import.py, upload_router.py
│   ├── ai_helper.py, whatsapp.py, password_links.py
│   ├── middleware.py, context_processors.py, templatetags/
│   └── migrations/
├── templates/          # Django templates (base, admin_dashboard, teacher)
├── static/ & staticfiles/
├── requirements.txt, Dockerfile, docker-compose.yml, render.yaml, Procfile
├── generate_data.py    # seed data
└── .venv/
```

## 4. Data Models (students/models.py)
- **StudentProfile** — linked to User; registration_number, branch, semester, contacts, admission year, password-change flags. Helpers: attendance %, set-password link, WhatsApp URL.
- **Subject** — branch/semester/subject_code/name/credits.
- **InternalExam** — CA1/CA2/CA3/MSE/Assignment/Attendance marks.
- **SemesterResult** — internal+external, auto grade calc, pass/fail.
- **Attendance** — per student/subject/date.
- **FacultyProfile** — staff user linked to subjects, permissions (notices/marks/materials), bio.
- **Assignment, StudyMaterial** — faculty uploads.
- **ClassSchedule** — weekday/time/room per subject+faculty.
- **Notice** — targeted by branch/semester.
- **CSVUpload** — tracks bulk imports with counters/errors.
- **BannerImage** — homepage banners.
- **Doubt / DoubtReply** — student Q&A forum.
- **FeeStructure / FeePayment** — fees management with receipts.
- **ExamSchedule** — exam timetable.
- **LeaveApplication** — student leave requests with review.
- **Feedback** — student→faculty/subject ratings.
- **Event** — college calendar.
- **WebsiteVisit** — analytics middleware logging.

## 5. Features / Modules
- **Auth:** student login/logout, set-password via token link, change password.
- **Student portal:** dashboard, profile edit, fees, exam schedule, leave apply, feedback, events, certificates, plane/college website pages.
- **Admin panel:** dashboard, CSV upload & history, students/teachers/admins CRUD, notices, subjects, marks/results entry, attendance (bulk), fees structures & payments, exam schedule, leave review, events, feedback report, reports, export CSV, export set-password links.
- **Teacher panel:** dashboard, students, take attendance, marks, assignments, materials, schedule, notices.
- **Banners:** upload/delete (admin+teacher).
- **Doubt forum:** list/detail/edit/delete + replies.
- **AI chatbot API:** `/api/ai-chat/`.
- **Analytics:** WebsiteVisitMiddleware logs visits.

## 6. URLs
See `students/urls.py` (single app). Root project urls include admin + app urls. Admin site at `/admin/`.

## 7. Settings Highlights
- DEBUG from env (default True), ALLOWED_HOSTS = ['*'] (permissive).
- SECRET_KEY has insecure fallback default.
- SQLite default; Postgres via env vars.
- WhiteNoise for static files.
- Custom middleware WebsiteVisitMiddleware.
- Context processor college_settings.
- Templates in BASE_DIR/templates.

## 8. Seed Data
`generate_data.py` is development-only: it refuses to run unless `DEBUG=True` and
`SEED_STUDENT_PASSWORD` is set, so no demo password is hardcoded or usable in production.
The admin superuser is created with `python manage.py createsuperuser`.

## 9. Deployment
- Render free tier (Postgres, gunicorn).
- Docker (python:3.12-slim) + compose with Postgres.
- Procfile for Heroku-style.

## 10. Potential Improvements (for the other AI to expand)
- Security: remove insecure SECRET_KEY fallback, restrict ALLOWED_HOSTS, add HTTPS/secure cookies, CSRF trusted origins, rate limiting.
- Auth: stronger password policy, 2FA, session security.
- Code quality: split views.py (very large), add tests (tests.py empty), type hints, linting.
- Performance: query optimization (select_related/prefetch), pagination, caching, indexes.
- Data: migrations review, validation, transactions in CSV import.
- Frontend: modernize templates, responsive design, accessibility.
- Features: notifications (email/WhatsApp actually wired), file size limits, audit logs.
- Observability: logging, error tracking (Sentry).
- API: REST/DRF instead of form-based, OpenAPI docs.
- Testing: unit/integration tests, CI.
- Database: use Postgres in dev parity, backups.
- i18n: multi-language.
- Remove plaintext-ish password handling; ensure token expiry.

## 11. Known Gaps / Risks
- No tests.
- `ALLOWED_HOSTS = ['*']` and insecure secret fallback.
- DEBUG default True.
- `.env` may be missing; defaults used.
- Large monolithic views.py.
- Mixed dev/prod config in docker-compose (DEBUG False but weak secret).
- Potential N+1 queries in list views.
- No input validation hardening on CSV uploads (file type/size).

---
Use this report to propose concrete, prioritized improvements.