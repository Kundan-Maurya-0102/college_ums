# Changelog

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
