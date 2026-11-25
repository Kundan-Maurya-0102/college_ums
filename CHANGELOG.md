# Changelog

## [1.0.0] — release candidate

First sellable release: one codebase, one deployment per college.

### Added
- **Parent portal** — `GuardianProfile` + `/parent/` (read-only attendance, marks, fees,
  notices for linked children); `manage.py add_guardian` issues a set-password link.
- **System status page** (`/admin-panel/system-status/`) — database, last backup with
  staleness flag, queued/failed jobs, media and disk usage, open errors, notification
  channel state.
- **Error tracking + daily digest** — ERROR/CRITICAL log records land in
  `students.ErrorEvent`; `manage.py send_error_digest` e-mails the super admin.
- **`manage.py diagnose_college <domain>`** — 13 checks (domain, DNS, DEBUG, secret,
  cookies, DB, migrations, static manifest, media, cache, SMTP connection, Twilio keys,
  queue, disk, backups), exit 0/1/2, `--json`.
- **`scripts/provision_server.sh`** — new-server deployment in one command, with
  generated secrets, optional `--restore`, and a diagnosis at the end.
- **`manage.py record_backup`** + backup bookkeeping shown in the status page.
- **`scripts/rc_flows.py`** — role-by-role HTTP walkthrough (admin, teacher, student,
  parent, super admin, anonymous).
- `docs/MULTI_COLLEGE_ISOLATION.md`, `CLAIM_AUDIT.md`, `CLEAN_START_REPORT.md`,
  `RELEASE_CHECKLIST.md`.

### Fixed
- `/platform/metrics/<slug>/` rejected every machine call (missing `csrf_exempt`).
- Per-college metrics tokens: one college could overwrite another's numbers.
- `EMAIL_*` settings did not exist; `notify('sms')` went out over the WhatsApp sender.
- `.dockerignore` `*.png` dropped the PWA icons, so a container build would 500.
- `pg_dump` missing produced an empty "valid" backup; `DB_ENGINE=postgres` broke Django;
  restore could not create a missing database.
- `SESSION/CSRF_COOKIE_SECURE` were hardcoded, blocking plain-HTTP staging logins.
- Fresh clone: staticfiles manifest test failure, `.env.example` inline comment crash,
  non-executable scripts, missing `create_college`.
- `manage.py test` no longer needs a `collectstatic` build.

### Security
- Per-college metrics tokens with constant-time comparison.
- Venv drift to Django 6.1.3 corrected; the suite runs on the pinned 4.2.30.
- bandit medium+ : 0; pip-audit: no findings outside Django 4.2 (9 advisories tracked).


Newest first. One section per round of work; each entry is something a college can
notice, plus the test that keeps it working.

## [Unreleased]

### Security
- **Media is no longer world-readable.** `/media/<path>` is served by Django with a login
  check; `csv_uploads/` (student PII) is staff-only; traversal outside `MEDIA_ROOT` is
  rejected. Opt out with `MEDIA_PROTECTED=False`. (`test_backlog_fixes.py`)
- **Admins are not superusers by default.** The Manage Admins form creates
  `is_staff=True, is_superuser=False`; only a superuser sees the "full superuser" box,
  and it is unchecked unless ticked. (`test_backlog_fixes.py`)

### UX
- Login failures now explain themselves: lockout says how many minutes remain, a live
  countdown appears and the page links to the set-password path instead of leaving the
  user guessing. (`test_backlog_fixes.py`)
- Hindi/English switch in the top bar and on the login page; 53 translated strings.
- Help Centre (`/help/`) with role-aware answers, keyboard shortcuts and a tour replay.
- First-login tour (2–3 steps, once per browser, Escape to close).
- Every form now shows a linked summary of validation errors instead of only red boxes.
- Mobile: fixed side-by-side grids collapse at 900/1024 px; tables become cards under
  640 px; empty states explain the next action.
- "Report a problem" button on every page → stored, triaged at `/admin-panel/bug-reports/`.

### Growth
- Public landing page at `/` with features, CSS screenshots, pricing from the plans table
  and a demo-request form that stores leads (`DemoRequest`).
- `manage.py seed_demo` builds a demo college (50 students / 8 teachers / attendance /
  marks / fees / notices / timetable) in one command; refuses to run in production.
- Single-student "Add student" form (previously CSV-only).

### Ops
- GitHub Actions: tests, migrations check, ruff, bandit, pip-audit and a `DEBUG=False`
  production-settings smoke job.
- `scripts/deploy.sh` (backup → build → migrate → health check → auto-rollback) and
  `scripts/update_all.sh` for every college at once.
- Structured logging (`LOG_FORMAT=json`), Sentry with PII scrubbing, `/healthz/` and a
  real `/readyz/` (database + cache), `docs/RUNBOOK.md`, `docs/DEPLOYMENT.md`.

### Docs
- `docs/USER_GUIDE.md`, `ONBOARDING_CHECKLIST.md`, `docs/TERMS_SLA_TEMPLATE.md`,
  `docs/UX_AUDIT.md`, `BACKLOG.md`.

## Earlier rounds

- Super Admin panel (`/platform/`): colleges, plans with feature flags, subscription
  expiry/read-only, suspend/resume, backups, usage stats, support tickets.
- Background jobs (django-q2) with in-job retries and inline fallback.
- Performance: 36 → 210 req/s at 100 users, dashboard 3→1 aggregate, query budgets.
- Privacy: legal pages, log redaction, export/anonymise, retention purge, encrypted
  backups (restore tested).
- Security hardening (OWASP), deployment stack, tests package, UI redesign.

See `git log` for the commit that belongs to each item.
