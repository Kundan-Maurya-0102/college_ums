# Admin panel — redesign report

The office/principal panel now shares the same shell as the student and teacher panels
(`partials/dash_shell.html`) and a single aggregate data module (`students/admin_data.py`).

## Dashboard

* **Six clickable stat cards** — total students, teachers, attendance today,
  fees collected this month, pending fees, leave waiting. Each card is a link to the
  page that explains the number (`/admin-panel/students/`, `/reports/`, `/fee-payments/`…).
* **Three charts** (vendored Chart.js, colours read from `--primary` / `--line` /
  `--muted`, so dark mode and a college's `PRIMARY_COLOR` apply automatically):
  students per branch (bar), fees collected per month (bar), attendance % for the last
  30 days (line). The pass rate is next to the attendance trend.
* **"Pay attention" panel** — five lowest-attendance students, five biggest fee
  defaulters, leave waiting, unresolved errors and the last backup date (or a red
  "never" when `BackupRecord` is empty).
* **Quick actions** — Add student, Upload CSV, Post notice, Add fee payment, Reports,
  Exam documents.
* **Recent activity** — last 8 `AuditLog` rows with who/what/when.

## Navigation

Grouped sidebar: Dashboard · Students (students, CSV, leave) · Staff · Academics
(subjects, attendance, marks, exams, exam documents) · Money (fee payments, structure) ·
Communication (notices, events, problem reports) · Reports (reports, feedback) ·
System (system status). The top menus are Students / Academics / Office, with a
students-only search box, a bell that summarises leave + unresolved errors, and a
profile menu.

`tests/test_admin_panel.py::AdminNavigationTests` asserts that an admin sees these
groups, that every sidebar link resolves, and that student-only pages
(`/dashboard/`, `/my-fees/`, `/leave-apply/`) **never** appear in the admin chrome.

## Data isolation and cost

* Every card, chart and panel is computed from the local database only; the cross-college
  test proves the branch chart and the activity feed contain exactly the local rows.
* All series are `GROUP BY` aggregates. With 10 extra students and their attendance the
  dashboard query count is unchanged (`test_dashboard_query_count_is_flat`).
* The perf test's budget was raised from 18 to 24 queries **because the page gained
  three charts, the attention panel and the audit feed** — the count is still constant
  in data size, which is the property that matters. Two aggregates that used to run
  twice (fee totals, leave pending, student lookups) now run once each.

## Fixed along the way

* `/admin-panel/fee-payments/`, `/reports/`, `/attendance/`, `/students/` overflowed a
  360 px screen (unwrapped tables, fixed filter widths) — tables now scroll in their own
  container and the filter rows wrap.
* `fee_payments.html` used a bare `<input>` with no label; it has a real label now.
* Removed a link to `college_backup` that only exists in the **super-admin** URLconf, so
  it would have 500'd for a college admin.

## Still open (needs a decision, not a fix)

* Only the **dashboard** moved onto the new shell so far. The other ~25 admin templates
  still extend `base.html` (same design tokens, older topbar/sidebar). Moving them is a
  mechanical follow-up and was left out to keep this change reviewable.
* Data tables on the remaining admin pages have search + pagination where the views
  already provided them; **bulk actions, sortable headers and a row actions menu do not
  exist** anywhere in the admin panel yet — that is a feature, not a restyle.
* Settings page for college branding (name/logo/colours preview) does not exist; today
  branding comes from `.env`.
* The "new admissions / inquiries" stat was left out because the admission module does
  not exist yet.
