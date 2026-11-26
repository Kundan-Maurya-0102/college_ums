# Student UI QA — report

Scope: every page a student can reach — dashboard, fees, exam schedule, hall ticket,
marksheet, exam documents, leave, feedback, events, certificates, forum, profile,
password change, notices, attendance, results, timetable, materials, help, privacy,
college website.

How it was checked (all real, no guessing):

1. **Link crawl** with the Django test client as `demo_student1`: 21 pages rendered,
   35 unique internal links opened, **0 broken links** (`/logout/` is a GET link by
   design — see "manual check").
2. **Real browser sweep** (headless Chrome via playwright, dev-only dependency) at
   **360 / 768 / 1280 px** × 21 pages = 63 page/viewport combinations. For each one:
   horizontal overflow, elements wider than the viewport, inline `style` attributes,
   hardcoded hex colours in the DOM, missing `<h1>`, images without `alt`, form fields
   without a label, links/buttons without an accessible name, console/JS errors.
3. **Contrast maths** in the browser (WCAG relative luminance, real resolved colours,
   `color-mix()` resolved through a canvas) for body text, `.muted`, `.small`, every
   badge variant and error text, in **light and dark** theme.
4. `python manage.py test` after every change.

## Result: 63/63 combinations with zero horizontal overflow, zero JS errors

Final state — `overflowX = 0` on every page at 360, 768 and 1280 px; light and dark
both pass 4.5:1 for body, muted, small, badge and error text.

## What was actually broken (and fixed)

| # | Problem | Fix |
|---|---------|-----|
| 1 | `static/css/style.css` — the old "Windows/phpMyAdmin" theme — was still loaded **after** `theme.css` on every page (hardcoded hex palette, Tahoma, 3D borders, `html{font-size:13px}`). | Deleted the file and its three `<link>` tags; the few helpers it still provided moved into `theme.css`. |
| 2 | Removing it exposed that `theme.css` had **no `box-sizing: border-box`** (the old file provided it), so every `width:100%` block with padding overflowed by exactly the padding (16/24/40 px). | Added the reset to `theme.css`. |
| 3 | About 30 class names used by the student pages had **no CSS rule at all**: `.muted`, `.small`, `.page-title`, `.mt-24`, `.mt-3`, `.ml-2`, `.field`, `.plain-list`, `.w-100`, `.h3-small`, `.stats-row`, `.stat-box/.stat-num/.stat-desc`, `.section-title/-label/-body`, `.card-student`, `.badge-student`, `.form-student`, `.form-help`, `.tag`, the whole `.pagination*` family, `.fieldset-student`. Each page fell back to browser defaults (grey text stayed black, lists got bullets, no spacing). | Defined them once in `theme.css` using the existing variables. |
| 4 | Fee / leave status badges used class names built from the status (`success`, `warning`, `danger`) that do not exist → **navy text on a light chip, 1.3:1 contrast**. | Mapped to the real `badge-green / badge-yellow / badge-red` variants. |
| 5 | Dark mode had **two switches**: `data-theme` (ui.js) and `.dash-dark` (dashboard.js) with a duplicated hex palette in `dashboard.css` that could drift. | One switch: `data-theme` on `<html>`, cookie-seeded server-side, duplicate palette deleted. |
| 6 | Dark-mode badges used the light-mode foregrounds on dark tinted chips (`--ok` on `--ok-bg` = 2.9:1). | Dark theme now overrides `--ok/--warn/--danger/--info` with lighter tones; all badge variants ≥ 5.8:1. |
| 7 | Active sidebar item in dark mode: `--primary` text on a `--primary-050` chip = dark on dark (the vision check caught it, maths confirmed). | `[data-theme="dark"] .sidebar-link.active` uses `--ink` on `--primary-100` (15.4:1). |
| 8 | `.muted` in light mode was 4.34:1 — just under AA. | Darkened `--muted` to `#556274` (5.66:1). |
| 9 | `templates/partials/bug_report.html` (the "Report a problem" dialog on **every** page) carried 9 inline styles. | Replaced with `.report-*` classes. |
| 10 | Certificate / ID-card page had 18 inline styles including a hardcoded `border:2px solid #000` and the now-undefined `var(--highlight)` (transparent seal). | `.cert-*` classes, seal uses `--primary` / `--on-primary`. |
| 11 | Doubt forum templates were old Bootstrap markup with `background:#fff` (a white card in dark mode) and inline `onclick`/`onmouseover` handlers. | Rewritten on the design system (`doubt_list`, `doubt_detail`, `doubt_form`, `reply_form`, both delete confirms): real `<label>`s, error `<p class="field-errors">`, empty states, keyboard-friendly links. |
| 12 | Header/footer areas of 4 money/exam/event pages had tables wider than a phone with no scroll container. | Wrapped in `.table-responsive`, which was then given `min-width:0` so it can shrink inside a flex column. |
| 13 | `/exam/documents/` and `/profile/edit/`, `/change-password/`, `/materials/`, dashboard skeleton had leftover inline styles. | Moved to classes (`--pct` ring value stays inline, it is data). |
| 14 | `certificates.html` table and `.btn-row/.req/.quote` needed by the rewritten forms. | Added to `theme.css`. |

## Performance

`students/tests/test_student_pages.py::StudentPageQueryBudgetTests` renders dashboard,
attendance, results, timetable and materials with 1 subject and then with 13 subjects:
**query count must not grow by more than 2** — it passes (aggregate queries only).

## Needs a manual check (cannot be verified from here)

- **Screen reader / keyboard-only pass** on the dashboard shell (menus, bell dropdown,
  search) — the DOM has labels and `aria-*`, but real NVDA/VoiceOver behaviour is
  untested.
- **`/logout/` is a GET link**. Logging out by following a link works, but a GET that
  changes state is CSRF-friendly (already listed as a backlog item). Changing it touches
  URLs/behaviour, which this task must not do.
- **PDF pages** (`/exam/hall-ticket/`, `/exam/marksheet/`) open in Chrome's PDF viewer, so
  their "no `<h1>`, inline styles" audit hits are the browser's viewer page, not ours.
  Zoom/print layout of the generated PDFs is worth a human look on paper.
- **Real iOS Safari / Android Chrome** layout (the sweep used desktop Chrome at mobile
  widths, which does not reproduce iOS safe-area/URL-bar behaviour).
- **Language switch** to Hindi on every page — translations exist, but a native speaker
  should read the student-facing strings once.
