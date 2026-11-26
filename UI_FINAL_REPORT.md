# UI final report — student, teacher and admin panels

Three panels, one design system. Release tag: **v1.1.0-ui**.

## What "consistent" means here now

| Layer | Before | Now |
|-------|--------|-----|
| Stylesheets | `style.css` (old Windows/phpMyAdmin theme, hardcoded hex, Tahoma) loaded **after** `theme.css` on every page | one `theme.css` (tokens + components) + `dashboard.css` (shell/cards). Old file deleted. |
| Shell | student dashboard had its own shell; teacher and admin used the older `base.html` topbar/sidebar | `partials/dash_shell.html` is the single shell; `student/shell.html`, `teacher/shell.html`, `admin_dashboard/shell.html` are thin overrides (menus, sidebar, search target, profile card, bell preview). |
| Dark mode | two switches (`data-theme` + `.dash-dark`) with a duplicated hex palette | one switch: `data-theme` on `<html>`, cookie-seeded on the server, panels share the same tokens. |
| Buttons / badges / tables / forms / empty states / toasts | mixed: Bootstrap-ish classes from the old forum/admin templates, ~30 classes with no rule at all | all defined once in `theme.css` (`.btn`, `.badge-*`, `.data-table`, `.form-control`, `.empty-state`, `.dash-empty`, `.alert`, `.field-errors`). |
| Language switch, onboarding tour, service worker | only on `base.html` | in the shared shell too, so all three panels have them. |

## Duplicates removed

* `static/css/style.css` (486 lines) — deleted with its three `<link>` tags.
* `.dash-dark` palette in `dashboard.css` — deleted (theme tokens only).
* Student shell markup — moved into the shared partial instead of a second copy.
* Forum templates rewritten off Bootstrap classes; certificate/ID card and the report
  dialog lost their inline styles (18 and 9 respectively → 0).
* A hardcoded Google Drive folder URL in the teacher materials page → `MATERIAL_SHARED_FOLDER_URL`.
* A link to the super-admin-only `college_backup` view inside the admin sidebar.

Inline `style=` attributes across `templates/student/**` and `templates/forum/**`: only the
skeleton widths, the attendance ring's `--pct` value and the icon sprite's
`display:none` remain — all of them carry data, not styling.

## Verification (all re-run at the end)

* `python manage.py test` → **442 tests OK** (was 399 at the start of this work).
* `scripts/ci.sh` → **CI mirror finished OK** (deploy check, pip-audit with no accepted
  advisories, migrations clean, production template engine, full suite).
* `scripts/rc_flows.py` against the live dev server → **111/111 checks passed**
  (admin, teacher, student, parent, super admin, anonymous). The five parent checks
  failed at first only because the demo database had no guardian; a guardian was added
  with `manage.py add_guardian`, which is how a real deployment creates one.
* Real Chrome (playwright, dev-only) sweep at **360 / 768 / 1280 px**:
  student 19 pages × 3 widths, teacher 8 pages × 3 widths, admin 10 pages × 3 widths —
  **zero horizontal overflow, zero JS errors**.
* WCAG contrast measured in the browser for body text, `.muted`, `.small`, every badge
  variant, error text, sidebar (active and idle) — **all ≥ 4.5:1 in light and dark**.
* Query budgets: student dashboard/pages, teacher dashboard/students list and admin
  dashboard are all constant in data size (tests add 10–13 rows and assert no growth).

## Honest gaps (not fixed here)

* Admin: only the dashboard uses the new shell; ~25 older admin templates still extend
  `base.html` (same tokens, older chrome). Bulk actions, sortable headers and a row
  actions menu do not exist anywhere in the admin panel.
* Teacher: marks entry is still one-student-at-a-time (no spreadsheet grid, no CSV
  import/export); students list has search but no sort/pagination.
* Student: `/logout/` is still a GET link (listed in `BACKLOG.md`); PDF pages
  (hall ticket, marksheet) are rendered by the browser's PDF viewer, so their layout
  needs a human look on paper.
* Manual checks that only a human can do are listed in `STUDENT_UI_REPORT.md`,
  `TEACHER_UI_REPORT.md` and `ADMIN_UI_REPORT.md` (screen reader passes, iOS Safari,
  Hindi copy review, keyboard-only attendance entry).
* Docker/Caddy still not installed in this environment, so the container image and TLS
  config remain unverified here.
