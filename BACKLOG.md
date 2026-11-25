# Backlog

Ranked by **impact on a college going live** (data safety and trust first, polish last).
Every item says where the code lives, so the next person does not have to rediscover it.

Legend: 🔴 blocks a sale / data-safety risk · 🟠 real friction for daily users ·
🟡 nice to have · ✅ done in this round (kept here for traceability)

| # | Item | Impact | Where | Status |
|---|---|---|---|---|
| 1 | `/media/` was served straight off disk by Caddy: a CSV upload containing student PII, or any assignment, was downloadable by anyone who knew the URL | 🔴 | `deploy/Caddyfile`, new `students/views/media.py` | ✅ |
| 2 | Creating an "Admin" from *Manage Admins* silently granted `is_superuser=True` — a clerk could reach the Django admin and change anything | 🔴 | `students/forms.py:AdminUserForm` | ✅ |
| 3 | Login lockout was indistinguishable from a wrong password, with no self-service way out | 🟠 | `students/views_student.py:student_login` | ✅ |
| 4 | Logout is a GET link (any page can log a user out with an `<img>` tag) | 🟠 | `students/views_student.py:student_logout`, `base.html` | open |
| 5 | ~~Django 4.2 → 5.2 LTS (9 advisories accepted in pip-audit)~~ | ✅ | `UPGRADE_NOTES.md` | done in v1.1.0 |
| 6 | Cache and sessions are locmem/db: the login lockout counter and rate limits reset on restart | 🟠 | `college_ums/settings.py` (`CACHES`, `SESSION_ENGINE`) | open |
| 7 | Plan feature flags (`College.has_feature()`) are stored but not used to hide menu items | 🟠 | `platform_admin/models.py`, `templates/base.html` | open |
| 8 | Study material and assignment files are still not scoped per branch/semester | 🟠 | `students/views/content.py` | open |
| 9 | ~25 long inline `style="…"` attributes remain (dashboard, banners, attendance) | 🟡 | `templates/admin_dashboard/*.html`, `theme.css` | open |
| 10 | Django's own `/admin/` change forms are unthemed; staff are pointed at the custom panel | 🟡 | `templates/admin/*` | open |
| 11 | Junk staff accounts with no profile (`123456`, `756299`, `952569`) still exist in the dev DB | 🟡 | data, not code | open |
| 12 | Certificate/PDF generation is browser-print only; no server-side PDF for the exam cell | 🟡 | `templates/student/certificates.html` | open |
| 13 | No automated visual regression (no headless browser on the build host) | 🟡 | `scripts/`, CI | open |
| 14 | Landing page screenshots are CSS placeholders, not real product captures | 🟡 | `templates/landing.html` | open |
| 15 | Parent portal is read-only via office-issued link; no self-service parent login | 🟡 | phase 7 scope | open |

## Done this round (details in CHANGELOG.md)

1. **Media protection** — `/media/<path>` now goes through Django: login required,
   `csv_uploads/` staff-only, path traversal blocked, `MEDIA_PROTECTED=False` to opt out.
   Caddy no longer exposes `/srv/media` directly.
2. **No accidental superusers** — the Manage Admins form creates staff admins
   (`is_staff=True, is_superuser=False`) by default; the superuser box is only rendered
   for a superuser and is off by default. Existing superusers keep their flag on edit.
3. **Lockout UX** — the login page now says exactly why it failed, how many minutes are
   left, and offers the "ask the office for a set-password link" path plus a live countdown.

## How to pick the next item

Take the highest 🔴 that a real college would hit in its first month, write the test
first (`students/tests/`), and keep the change under ~150 lines so a rollback is cheap.
