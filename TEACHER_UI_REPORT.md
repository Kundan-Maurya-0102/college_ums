# Teacher panel — redesign report

Goal: the teacher panel now uses the same shell, cards, colours and spacing as the
student portal, arranged around a teacher's day instead of a student's.

## One shell, three panels

`templates/student/shell.html` was split into **`templates/partials/dash_shell.html`**
with blocks (`brand_url`, `portal_label`, `dash_menus`, `search_action`,
`search_placeholder`, `bell_items`, `bell_all_url`, `profile_menu`, `dash_sidebar`).
The student shell is now a two-line file that extends it with the defaults, and
`templates/teacher/shell.html` overrides only the navigation parts. The rendered
student pages are byte-identical in structure (all 37 dashboard/page tests still pass).

## Teacher dashboard (new)

`students/teacher_data.py` builds everything in aggregates:

| Card | Data | Queries |
|------|------|---------|
| Today's classes (with "Attendance done"/"Take attendance") | `ClassSchedule` for today + today's `Attendance` presence | 2 |
| Pending work (attendance not taken, marks missing, assignments past due, leave waiting) | subject list + scoped counts | 2 |
| My subjects (class size, classes held, avg attendance, quick links) | grouped `Count` over students + attendance | 2 |
| Low attendance (top 5, colour-coded) | one grouped attendance query + `in_bulk` | 3 |
| Doubts to answer | unresolved doubts of the teacher's classes | 1 |
| Notices & uploads | own notices + `StudyMaterial` | 2 |
| Exams & events | `ExamSchedule` for own subjects + `Event` | 2 |

Quick-action row: Take attendance · Enter marks · Upload material · Add assignment ·
Post notice · My students — all existing URLs, nothing invented.

`test_teacher_panel.py` asserts the query count stays flat when 12 more students are
added, that another teacher's subjects/students never appear, and that students
cannot open any `/teacher/` page.

## Pages moved onto the shell

`take_attendance`, `marks`, `students`, `notices`, `notice_form`,
`notice_delete_confirm`, `content_form` (assignments / materials / schedule) all
extend `teacher/shell.html` now, and all inline styles were replaced with classes.
The pages that were plain `base.html` had a **500** for any teacher view that did not
pass `faculty` (the shell read a variable that only the dashboard set) — fixed with a
`{% with teacher=faculty|default:request.user.facultyprofile %}` fallback.

## Attendance page

Rewritten: "All present / All absent / Invert" one-click buttons, a live
`present / absent` counter next to the save button and in the card header (also
announced through `aria-live`), a sticky save bar on a phone, Tab/Space friendly
checkboxes with an `aria-label` per student, and a double-submit guard
(`static/js/teacher-attendance.js`). Without JS the form still works — every box
starts ticked and the plain submit posts the same field names as before.

## Students list

Was **2 queries per row** (`get_attendance_percentage()`); now one grouped
attendance query plus `in_bulk`. Added a search box (name or registration number)
that only searches inside the selected class. A student with no marked classes shows
`—` instead of a misleading `0%`.

## Marks page

Responsive filter row (was a fixed 4-column grid overflowing at 360 px), form fields
with real `<label for>` and `<p class="field-errors">`, two-column layout that
collapses under 1000 px. The entry flow, field names and validation were not changed.

## Bug found and removed: a hardcoded college link

`templates/teacher/content_form.html` shipped a **fixed Google Drive folder ID** in
the "Note / PDF" card — one college's private link inside a product sold to others.
Now `MATERIAL_SHARED_FOLDER_URL` in `.env` (see `.env.example`); blank hides the
button.

## Verification

* Every teacher page renders 200 for a teacher, redirects for a student/anonymous.
* Real-Chrome sweep at **360 / 768 / 1280**: `overflowX = 0`, no JS errors, no element
  outside the viewport on all 8 teacher pages.
* Full suite: **431 tests OK**, `ruff` clean.

## Needs a manual check (could not verify here)

- Keyboard-only walk of the attendance sheet (Tab order across 60 students, Space to
  toggle) on a real browser + screen reader.
- The marks "spreadsheet" asked for in the brief is **not** built as Tab/Enter cell
  grid; the page still posts one student at a time through the existing
  `InternalExamForm`. Changing that means changing the form/view contract, which this
  task had to leave alone. Listed as follow-up.
- CSV import/export of marks does not exist yet (never did) — follow-up.
- Students list has search but no sort/pagination controls; classes are small in the
  demo, but a 200-student branch would need pagination.
- Print layout of any teacher page (none was designed for print).
